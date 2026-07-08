import { expect, test } from '@playwright/test';

/** Connectors settings UI against a REAL external MCP fixture server. */

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
			data: { name: 'Connectors E2E' },
			headers: { Authorization: `Bearer ${session.access}` }
		})
	).json();
	workspaceId = workspace.id;
});

async function openSettings(page: import('@playwright/test').Page) {
	await page.addInitScript((stored) => {
		localStorage.setItem('cyberarche.session', JSON.stringify(stored));
	}, session);
	await page.goto(`/w/${workspaceId}/settings`);
	await page.getByTestId('connector-name').waitFor();
}

test('attach a real MCP server, see its namespaced tools, toggle, remove', async ({
	page
}) => {
	await openSettings(page);

	// Unreachable endpoints are rejected by the live handshake.
	await page.getByTestId('connector-name').fill('Ghost');
	await page.getByTestId('connector-endpoint').fill('http://127.0.0.1:9/mcp/');
	await page.getByTestId('connector-add').click();
	await expect(page.getByTestId('connector-error')).toBeVisible({ timeout: 20_000 });

	// The real fixture server attaches successfully.
	await page.getByTestId('connector-name').fill('Ticketing');
	await page.getByTestId('connector-endpoint').fill('http://127.0.0.1:8200/mcp/');
	await page.getByTestId('connector-add').click();

	const row = page.getByTestId('connector-row');
	await expect(row).toHaveCount(1, { timeout: 20_000 });
	await expect(row).toContainText('ticketing');
	await expect(page.getByTestId('connector-tool')).toContainText(
		'ticketing__get_ticket_status'
	);

	// Disable -> tools disappear; re-enable -> they return.
	await page.getByTestId('connector-toggle').uncheck();
	await expect(page.getByTestId('connector-tool')).toHaveCount(0);
	await page.getByTestId('connector-toggle').check();
	await expect(page.getByTestId('connector-tool')).toHaveCount(1);

	// The agent panel surfaces the external tools for this workspace.
	const doc = await page.evaluate(async (stored) => {
		const response = await fetch('/api/v1/documents', {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
				Authorization: `Bearer ${stored.access}`
			},
			body: JSON.stringify({ workspace_id: location.pathname.split('/')[2], title: 'Tools' })
		});
		return response.json();
	}, session);
	await page.goto(`/w/${workspaceId}/d/${doc.id}`);
	await page.getByTestId('agent-toggle').click();
	await page.getByTestId('agent-tools-toggle').click();
	await expect(page.getByTestId('agent-tools-toggle')).toContainText('1 external · 1 MCP');
	await expect(page.getByTestId('agent-tools')).toContainText('Ticketing');

	// Remove from settings.
	await page.getByTestId('open-settings').click();
	await page.getByTestId('connector-remove').click();
	await expect(page.getByTestId('no-connectors')).toBeVisible();
});
