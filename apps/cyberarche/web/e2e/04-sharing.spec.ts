import { expect, test, type Page } from '@playwright/test';

/** Share dialog + block comments against the real backend. */

const EMAIL = process.env.CYBERARCHE_IT_EMAIL ?? '';
const PASSWORD = process.env.CYBERARCHE_IT_PASSWORD ?? '';

test.skip(!EMAIL || !PASSWORD, 'CYBERARCHE_IT_EMAIL / _PASSWORD not configured');

let session: { access: string; refresh: string };
let workspaceId: string;

test.beforeAll(async ({ request }) => {
	let tokens: { access_token?: string; refresh_token?: string } = {};
	for (const delay of [0, 2000, 5000, 10_000]) {
		if (delay) await new Promise((resolve) => setTimeout(resolve, delay));
		const login = await request.post('http://127.0.0.1:8123/api/v1/auth/session', {
			data: { email: EMAIL, password: PASSWORD }
		});
		if (login.ok()) {
			tokens = await login.json();
			break;
		}
	}
	if (!tokens.access_token) throw new Error('e2e login failed after retries');
	session = { access: tokens.access_token!, refresh: tokens.refresh_token! };
	const workspace = await (
		await request.post('http://127.0.0.1:8123/api/v1/workspaces', {
			data: { name: 'Sharing E2E' },
			headers: { Authorization: `Bearer ${session.access}` }
		})
	).json();
	workspaceId = workspace.id;
});

async function openDocument(
	page: Page,
	request: import('@playwright/test').APIRequestContext
): Promise<string> {
	const document = await (
		await request.post('http://127.0.0.1:8123/api/v1/documents', {
			data: { workspace_id: workspaceId, title: `Share Doc ${Date.now()}` },
			headers: { Authorization: `Bearer ${session.access}` }
		})
	).json();
	await page.addInitScript((stored) => {
		localStorage.setItem('cyberarche.session', JSON.stringify(stored));
	}, session);
	await page.goto(`/w/${workspaceId}/d/${document.id}`);
	await page.getByTestId('block-editor').waitFor();
	return document.id;
}

test('share dialog: create a view link, then revoke it', async ({ page, request }) => {
	await openDocument(page, request);

	await page.getByTestId('share-open').click();
	const dialog = page.getByTestId('share-dialog');
	await expect(dialog).toBeVisible();

	await dialog.getByTestId('create-link').click();
	const link = dialog.getByTestId('share-link').first();
	await expect(link).toBeVisible();
	await expect(link).toContainText('view');
	await expect(link.locator('code')).toContainText('/share/');

	await link.getByTestId('revoke-link').click();
	await expect(link).toContainText('revoked');
});

test('comments: add on a block, visible after reload, then resolve', async ({
	page,
	request
}) => {
	await openDocument(page, request);

	// Open the comment thread from the block gutter.
	const row = page.locator('.row').first();
	await row.hover();
	await row.getByTestId('block-comments').click();

	const thread = page.getByTestId('comment-thread');
	await thread.getByTestId('comment-input').fill('Please tighten this paragraph');
	await thread.getByTestId('comment-input').press('Enter');
	await expect(thread.getByTestId('comment')).toHaveCount(1);
	await expect(thread).toContainText('tighten this paragraph');

	// Comments persist server-side (visible to other participants).
	await page.reload();
	await page.getByTestId('block-editor').waitFor();
	const rowAfter = page.locator('.row').first();
	await rowAfter.hover();
	await rowAfter.getByTestId('block-comments').click();
	await expect(page.getByTestId('comment')).toHaveCount(1);

	// Resolve clears it from the open thread.
	await page.getByTestId('resolve-comment').click();
	await expect(page.getByTestId('comment')).toHaveCount(0);
});
