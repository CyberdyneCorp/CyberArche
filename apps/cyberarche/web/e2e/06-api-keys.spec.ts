import { expect, test } from '@playwright/test';

import { loadSession, type Session } from './session';

/** API keys: minted in the UI, usable as an MCP-client credential, revocable. */

const EMAIL = process.env.CYBERARCHE_IT_EMAIL ?? '';
const PASSWORD = process.env.CYBERARCHE_IT_PASSWORD ?? '';

test.skip(!EMAIL || !PASSWORD, 'CYBERARCHE_IT_EMAIL / _PASSWORD not configured');

let session: Session;
let workspaceId: string;

test.beforeAll(async ({ request }) => {
	session = loadSession();
	const workspace = await (
		await request.post('http://127.0.0.1:8123/api/v1/workspaces', {
			data: { name: 'API Keys E2E' },
			headers: { Authorization: `Bearer ${session.access}` }
		})
	).json();
	workspaceId = workspace.id;
});

test('create in UI (shown once), authenticate like an MCP client, revoke', async ({
	page,
	request
}) => {
	await page.addInitScript((stored) => {
		localStorage.setItem('cyberarche.session', JSON.stringify(stored));
	}, session);
	await page.goto(`/w/${workspaceId}/settings`);
	await page.getByTestId('settings-tab-keys').click(); // API keys live on their tab

	// Create a key; the secret appears exactly once.
	await page.getByTestId('apikey-name').fill('Claude Desktop');
	await page.getByTestId('apikey-create').click();
	const secretBox = page.getByTestId('apikey-secret-box');
	await expect(secretBox).toBeVisible();
	const secret = (await page.getByTestId('apikey-secret').textContent())!.trim();
	expect(secret.startsWith('cak_')).toBe(true);

	await page.getByTestId('apikey-dismiss').click();
	await expect(secretBox).toHaveCount(0); // gone for good
	await expect(page.getByTestId('apikey-row')).toContainText('cak_');
	await expect(page.getByTestId('apikey-row')).not.toContainText(secret);

	// The key authenticates exactly like an external MCP client's Bearer
	// credential (same token seam the MCP server verifies).
	const asKey = { Authorization: `Bearer ${secret}` };
	const viaKey = await request.get('http://127.0.0.1:8123/api/v1/workspaces', {
		headers: asKey
	});
	expect(viaKey.ok()).toBe(true);
	expect((await viaKey.json()).some((w: { id: string }) => w.id === workspaceId)).toBe(
		true
	);

	// Revoke in the UI -> the credential dies immediately.
	await page.getByTestId('apikey-revoke').click();
	await expect(page.getByTestId('apikey-row')).toContainText('revoked');
	const denied = await request.get('http://127.0.0.1:8123/api/v1/workspaces', {
		headers: asKey
	});
	expect(denied.status()).toBe(401);
});
