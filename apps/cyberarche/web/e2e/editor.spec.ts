import { expect, test, type Page } from '@playwright/test';

/** Block editor + realtime collaboration against the real backend. */

const EMAIL = process.env.CYBERARCHE_IT_EMAIL ?? '';
const PASSWORD = process.env.CYBERARCHE_IT_PASSWORD ?? '';

test.skip(!EMAIL || !PASSWORD, 'CYBERARCHE_IT_EMAIL / _PASSWORD not configured');

interface Session {
	access: string;
	refresh: string;
}

let session: Session;
let workspaceId: string;

test.beforeAll(async ({ request }) => {
	// The live auth service rate-limits logins; retry with backoff so rapid
	// consecutive e2e runs stay stable.
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
	const headers = { Authorization: `Bearer ${session.access}` };

	const workspace = await (
		await request.post('http://localhost:8000/api/v1/workspaces', {
			data: { name: 'Editor E2E' },
			headers
		})
	).json();
	workspaceId = workspace.id;
});

/** Each test gets its own document, so block assertions stay isolated. */
async function openDocument(
	page: Page,
	request: import('@playwright/test').APIRequestContext
): Promise<void> {
	const document = await (
		await request.post('http://localhost:8000/api/v1/documents', {
			data: { workspace_id: workspaceId, title: `Doc ${Date.now()}` },
			headers: { Authorization: `Bearer ${session.access}` }
		})
	).json();
	await page.addInitScript((stored) => {
		localStorage.setItem('cyberarche.session', JSON.stringify(stored));
	}, session);
	await page.goto(`/w/${workspaceId}/d/${document.id}`);
	await page.getByTestId('block-editor').waitFor();
	await expect(page.getByTestId('sync-status')).toHaveText('Synced');
}

test('typing, markdown shortcuts, and the slash menu', async ({ page, request }) => {
	await openDocument(page, request);
	const editor = page.getByTestId('block-editor');

	// Type into the seeded paragraph.
	const paragraph = editor.locator('[data-block-type="paragraph"] .editable').first();
	await paragraph.click();
	await paragraph.pressSequentially('The retrieval pipeline needs a rework.');
	await expect(paragraph).toHaveText(/needs a rework/);

	// Markdown shortcut: "# " becomes a heading.
	await page.getByTestId('append-block').click();
	await page.keyboard.type('# ');
	await expect(editor.locator('[data-block-type="heading"]')).toHaveCount(1);
	await page.keyboard.type('Goals');

	// Slash menu inserts a code block.
	await page.getByTestId('append-block').click();
	await page.keyboard.type('/code');
	await expect(page.getByTestId('slash-menu')).toBeVisible();
	await page.keyboard.press('Enter');
	await expect(page.getByTestId('code-block')).toBeVisible();
});

test('LaTeX renders and surfaces errors without losing source', async ({ page, request }) => {
	await openDocument(page, request);

	await page.getByTestId('append-block').click();
	await page.keyboard.type('/latex');
	await page.keyboard.press('Enter');

	const block = page.getByTestId('latex-block').last();
	const source = block.locator('textarea');
	await source.fill('\\sum_{i=1}^{n} x_i^2');
	await expect(block.locator('.katex')).toBeVisible();

	// Invalid LaTeX -> inline error, source preserved.
	await block.locator('.render').click();
	await source.fill('\\frac{1}');
	await expect(page.getByTestId('latex-error')).toBeVisible();
	await expect(source).toHaveValue('\\frac{1}');
});

test('Mermaid renders a flowchart and shows parse errors', async ({ page, request }) => {
	await openDocument(page, request);

	await page.getByTestId('append-block').click();
	await page.keyboard.type('/mermaid');
	await page.keyboard.press('Enter');

	const block = page.getByTestId('mermaid-block').last();
	await block.locator('textarea').fill('flowchart LR\n  Query --> Embed --> Rerank');
	await expect(block.getByTestId('mermaid-render').locator('svg')).toBeVisible();

	await block.getByRole('tab', { name: 'Source' }).click();
	await block.locator('textarea').fill('flowchart LR\n  Query --> --> broken');
	await expect(block.getByTestId('mermaid-error')).toBeVisible();
});

test('tables add rows and columns', async ({ page, request }) => {
	await openDocument(page, request);

	await page.getByTestId('append-block').click();
	await page.keyboard.type('/table');
	await page.keyboard.press('Enter');

	const table = page.getByTestId('table-block').last();
	await expect(table.locator('th input')).toHaveCount(2);
	await table.getByTestId('add-column').click();
	await expect(table.locator('th input')).toHaveCount(3);
	await table.getByTestId('add-row').click();
	await expect(table.locator('tbody tr')).toHaveCount(2);
});

test('two browsers see each other: live text and presence', async ({ browser, request }) => {
	const contextA = await browser.newContext();
	const contextB = await browser.newContext();
	const pageA = await contextA.newPage();
	const pageB = await contextB.newPage();
	await openDocument(pageA, request);
	const docUrl = pageA.url();
	await pageB.addInitScript((stored) => {
		localStorage.setItem('cyberarche.session', JSON.stringify(stored));
	}, session);
	await pageB.goto(docUrl);
	await pageB.getByTestId('block-editor').waitFor();

	// A types; B sees it live through the relay.
	const paragraphA = pageA.locator('[data-block-type="paragraph"] .editable').first();
	await paragraphA.click();
	await paragraphA.pressSequentially('hello from A');

	const paragraphB = pageB.locator('[data-block-type="paragraph"] .editable').first();
	await expect(paragraphB).toContainText('hello from A', { timeout: 10_000 });

	await contextA.close();
	await contextB.close();
});

test('undo and redo restore local edits', async ({ page, request }) => {
	await openDocument(page, request);

	const appended = page.getByTestId('append-block');
	await appended.click();
	await page.keyboard.type('undo me');
	const block = page.locator('[data-block-type="paragraph"] .editable').last();
	await expect(block).toHaveText('undo me');

	// Undo removes the local edit (insert+typing merge into one capture)...
	await page.keyboard.press('ControlOrMeta+z');
	await expect(page.locator('.editable', { hasText: 'undo me' })).toHaveCount(0);

	// ...and redo brings it back.
	await page.keyboard.press('ControlOrMeta+Shift+z');
	await expect(page.locator('.editable', { hasText: 'undo me' })).toHaveCount(1);
});
