import { expect, request, test, type APIRequestContext } from '@playwright/test';

/** Smoke checks against the DEPLOYED instance. See playwright.smoke.config.ts.
 *
 * Read-mostly: the only mutation is one throwaway document, created and then
 * trashed + purged in the same run. Everything authenticates as the
 * CYBERARCHE_IT_* test user through the app's own session endpoint.
 */

const API =
	process.env.CYBERARCHE_SMOKE_API_URL ?? 'https://cyberarche.backend.coolify.cyberdynecorp.ai';
const MCP =
	process.env.CYBERARCHE_SMOKE_MCP_URL ?? 'https://cyberarche.mcp.coolify.cyberdynecorp.ai';
const email = process.env.CYBERARCHE_IT_EMAIL;
const password = process.env.CYBERARCHE_IT_PASSWORD;

test.describe('deployed smoke', () => {
	test.skip(!email || !password, 'CYBERARCHE_IT_EMAIL / _PASSWORD not set');

	let api: APIRequestContext;
	let access: string;

	test.beforeAll(async () => {
		api = await request.newContext({ baseURL: API });
		const response = await api.post('/api/v1/auth/session', { data: { email, password } });
		expect(response.ok(), `login failed: ${response.status()}`).toBe(true);
		access = (await response.json()).access_token;
	});

	test.afterAll(async () => {
		await api.dispose();
	});

	const auth = () => ({ Authorization: `Bearer ${access}` });

	test('api health is green', async () => {
		const response = await api.get('/api/v1/health');
		expect(response.ok()).toBe(true);
	});

	test('mcp health is green', async () => {
		const mcp = await request.newContext();
		const response = await mcp.get(`${MCP}/health`);
		expect(response.ok()).toBe(true);
		await mcp.dispose();
	});

	test('auth is enforced: no token means 401', async () => {
		const response = await api.get('/api/v1/workspaces');
		expect(response.status()).toBe(401);
	});

	test('workspaces list for the test user', async () => {
		const response = await api.get('/api/v1/workspaces', { headers: auth() });
		expect(response.ok()).toBe(true);
		const workspaces = await response.json();
		expect(Array.isArray(workspaces)).toBe(true);
		expect(workspaces.length).toBeGreaterThan(0);
	});

	test('document lifecycle: create, read, trash, purge', async () => {
		const workspaces = await (await api.get('/api/v1/workspaces', { headers: auth() })).json();
		const workspaceId = workspaces[0].id;

		const created = await api.post('/api/v1/documents', {
			headers: auth(),
			data: { workspace_id: workspaceId, title: `smoke-${Date.now()}` }
		});
		expect(created.status()).toBe(201);
		const documentId = (await created.json()).id;

		const read = await api.get(`/api/v1/documents/${documentId}`, { headers: auth() });
		expect(read.ok()).toBe(true);

		const trashed = await api.delete(`/api/v1/documents/${documentId}`, { headers: auth() });
		expect(trashed.ok()).toBe(true);
		const purged = await api.delete(`/api/v1/documents/${documentId}/trash`, {
			headers: auth()
		});
		expect(purged.ok()).toBe(true);
	});

	test('web app serves the SPA and sign-in works', async ({ page }) => {
		await page.goto('/');
		await page.waitForURL(/signin/);
		await page.getByPlaceholder('you@company.com').fill(email!);
		await page.locator('input[type="password"]').fill(password!);
		await page.getByRole('button', { name: /sign in/i }).click();
		// Leaving /signin into a workspace proves SPA + API + live auth wiring.
		await page.waitForURL((url) => !url.pathname.includes('signin'), { timeout: 15_000 });
	});
});
