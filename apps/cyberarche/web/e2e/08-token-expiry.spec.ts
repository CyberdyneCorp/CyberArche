import { expect, test } from '@playwright/test';

import { loadSession, API, type Session } from './session';

/** Production defect: the realtime endpoint closed the socket BEFORE accepting
 * it, so Starlette answered the handshake with HTTP 403 and the application
 * close code never reached the browser. The client could not tell an expired
 * token (refresh and retry) from a forbidden document (stop), so it retried a
 * dead token forever — "WebSocket connection failed", endlessly.
 *
 * These run in a real browser against the real backend, because the close code
 * only survives the real handshake; a stubbed socket would prove nothing. */

const EMAIL = process.env.CYBERARCHE_IT_EMAIL ?? '';
const PASSWORD = process.env.CYBERARCHE_IT_PASSWORD ?? '';

test.skip(!EMAIL || !PASSWORD, 'CYBERARCHE_IT_EMAIL / _PASSWORD not configured');

let session: Session;
let workspaceId: string;
let documentId: string;

test.beforeAll(async ({ request }) => {
	session = loadSession();
	const headers = { Authorization: `Bearer ${session.access}` };
	const workspace = await (
		await request.post(`${API}/api/v1/workspaces`, { data: { name: 'Expiry E2E' }, headers })
	).json();
	workspaceId = workspace.id;
	const document = await (
		await request.post(`${API}/api/v1/documents`, {
			data: { workspace_id: workspaceId, title: 'Expiry' },
			headers
		})
	).json();
	documentId = document.id;
});

/** Open a raw WebSocket in the page and report how it ended. */
async function closeCode(page: import('@playwright/test').Page, token: string) {
	return page.evaluate(
		([api, id, tok]) =>
			new Promise<{ code: number; received: boolean }>((resolve) => {
				let received = false;
				const ws = new WebSocket(`${api.replace(/^http/, 'ws')}/api/v1/documents/${id}/sync?token=${tok}`);
				ws.onmessage = () => (received = true);
				ws.onclose = (event) => resolve({ code: event.code, received });
				setTimeout(() => resolve({ code: -1, received }), 10_000);
			}),
		[API, documentId, token] as const
	);
}

test('a rejected socket tells the browser WHY: 4401, not an opaque failure', async ({ page }) => {
	await page.goto('/signin');

	const spent = await closeCode(page, 'spent.token.value');
	// The server accepts the handshake, then closes with the reason — that is
	// the only way an application close code reaches a browser. Before the fix
	// the handshake was denied outright and this was an opaque 1006.
	expect(spent.code).toBe(4401);
	expect(spent.received).toBe(false); // refused: no document state was sent
});

test('an unknown document closes 4404, distinguishable from an auth failure', async ({ page }) => {
	await page.goto('/signin');

	const missing = await page.evaluate(
		([api, tok]) =>
			new Promise<number>((resolve) => {
				const ws = new WebSocket(`${api.replace(/^http/, 'ws')}/api/v1/documents/does-not-exist/sync?token=${tok}`);
				ws.onclose = (event) => resolve(event.code);
				setTimeout(() => resolve(-1), 10_000);
			}),
		[API, session.access] as const
	);

	expect(missing).toBe(4404);
});

test('a valid token still connects and syncs the document', async ({ page }) => {
	await page.addInitScript((stored) => {
		localStorage.setItem('cyberarche.session', JSON.stringify(stored));
	}, session);
	await page.goto(`/w/${workspaceId}/d/${documentId}`);
	await expect(page.getByTestId('sync-status')).toHaveText('Synced');
});
