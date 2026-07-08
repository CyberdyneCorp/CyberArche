import { expect, test, type Page } from '@playwright/test';

/** Agent panel against the real backend with a REAL LLM provider.
 * Requires CYBERARCHE_IT_OPENAI_KEY in addition to the auth test user. */

const EMAIL = process.env.CYBERARCHE_IT_EMAIL ?? '';
const PASSWORD = process.env.CYBERARCHE_IT_PASSWORD ?? '';
const LLM_KEY = process.env.CYBERARCHE_IT_OPENAI_KEY ?? '';

test.skip(
	!EMAIL || !PASSWORD || !LLM_KEY,
	'CYBERARCHE_IT_EMAIL / _PASSWORD / _OPENAI_KEY not configured'
);

let session: { access: string; refresh: string };
let workspaceId: string;

test.beforeAll(async ({ request }) => {
	let tokens: { access_token?: string; refresh_token?: string } = {};
	for (const delay of [0, 2000, 5000, 10_000]) {
		if (delay) await new Promise((resolve) => setTimeout(resolve, delay));
		const login = await request.post('http://localhost:8000/api/v1/auth/session', {
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
		await request.post('http://localhost:8000/api/v1/workspaces', {
			data: { name: 'Agent E2E' },
			headers: { Authorization: `Bearer ${session.access}` }
		})
	).json();
	workspaceId = workspace.id;
});

async function openDocumentWithContent(
	page: Page,
	request: import('@playwright/test').APIRequestContext
): Promise<string> {
	const headers = { Authorization: `Bearer ${session.access}` };
	const document = await (
		await request.post('http://localhost:8000/api/v1/documents', {
			data: { workspace_id: workspaceId, title: 'Launch Plan' },
			headers
		})
	).json();
	// Seed known content the agent must ground on.
	await request.post(`http://localhost:8000/api/v1/documents/${document.id}/agent/blocks`, {
		data: {
			blocks: [
				{
					id: 'seed1',
					type: 'paragraph',
					data: { text: 'The launch codename is Bluebird and the launch date is March 3rd.' }
				}
			]
		},
		headers
	});
	await page.addInitScript((stored) => {
		localStorage.setItem('cyberarche.session', JSON.stringify(stored));
	}, session);
	await page.goto(`/w/${workspaceId}/d/${document.id}`);
	await page.getByTestId('block-editor').waitFor();
	await page.getByTestId('agent-toggle').click();
	await page.getByTestId('agent-panel').waitFor();
	return document.id;
}

test('ask: the agent answers grounded in the document (real LLM)', async ({
	page,
	request
}) => {
	test.setTimeout(90_000);
	await openDocumentWithContent(page, request);

	await page.getByTestId('agent-prompt').fill('What is the launch codename? Answer briefly.');
	await page.getByTestId('agent-prompt').press('Enter');

	const thread = page.getByTestId('agent-thread');
	await expect(thread.locator('.bubble.agent').last()).toContainText(/bluebird/i, {
		timeout: 60_000
	});
});

test('summarize and insert as block puts agent content into the live doc', async ({
	page,
	request
}) => {
	test.setTimeout(120_000);
	await openDocumentWithContent(page, request);

	await page.getByTestId('agent-summarize').click();
	const insert = page.getByTestId('insert-as-block');
	await expect(insert).toBeVisible({ timeout: 60_000 });

	const blocksBefore = await page.locator('[data-block-id]').count();
	await insert.click();
	await expect(insert).toHaveText(/Inserted/, { timeout: 15_000 });
	// The agent's blocks arrive through the CRDT relay into the open editor.
	await expect
		.poll(async () => page.locator('[data-block-id]').count(), { timeout: 15_000 })
		.toBeGreaterThan(blocksBefore);

	// The run is audited.
	await page.getByTestId('agent-runs-toggle').click();
	await expect(page.getByTestId('agent-runs')).toContainText(/Summarize|summarize/);
});

test('CSV ingestion creates a table block in the document', async ({ page, request }) => {
	test.setTimeout(90_000);
	await openDocumentWithContent(page, request);

	const csv = 'name,score\nada,99\ngrace,97\n';
	await page
		.locator('.chip-btn.ingest input[type="file"]')
		.setInputFiles({ name: 'scores.csv', mimeType: 'text/csv', buffer: Buffer.from(csv) });

	await expect(page.getByTestId('agent-thread')).toContainText(/Ingested scores\.csv/, {
		timeout: 30_000
	});
	// The extracted table lands in the live editor via the CRDT.
	await expect(page.getByTestId('table-block')).toBeVisible({ timeout: 15_000 });
	await expect(page.getByTestId('table-block').locator('th input').first()).toHaveValue(
		'name'
	);
});
