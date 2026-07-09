import { expect, test, type Page } from '@playwright/test';

import { loadSession, type Session } from './session';

/** Block editor + realtime collaboration against the real backend. */

const EMAIL = process.env.CYBERARCHE_IT_EMAIL ?? '';
const PASSWORD = process.env.CYBERARCHE_IT_PASSWORD ?? '';

test.skip(!EMAIL || !PASSWORD, 'CYBERARCHE_IT_EMAIL / _PASSWORD not configured');

let session: Session;
let workspaceId: string;

test.beforeAll(async ({ request }) => {
	session = loadSession();
	const headers = { Authorization: `Bearer ${session.access}` };

	const workspace = await (
		await request.post('http://127.0.0.1:8123/api/v1/workspaces', {
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
		await request.post('http://127.0.0.1:8123/api/v1/documents', {
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

test('undo/redo re-sync a focused block in place (not only on removal)', async ({
	page,
	request
}) => {
	await openDocument(page, request);
	const editor = page.getByTestId('block-editor');
	const paragraph = editor.locator('[data-block-type="paragraph"] .editable').first();
	await paragraph.click();
	await paragraph.pressSequentially('First');
	// Let the ~500ms undo capture window close so the next edit is its own step —
	// undo then reverts only the text and the block (and focus) survive.
	await page.waitForTimeout(650);
	await paragraph.pressSequentially(' draft');
	await expect(paragraph).toHaveText('First draft');

	// The bug: a focused contenteditable did not re-render on undo, so the last
	// edit stayed visible. Cmd/Ctrl+Z must revert the text in place.
	await page.keyboard.press('ControlOrMeta+z');
	await expect(paragraph).toHaveText('First');

	// Redo re-applies it.
	await page.keyboard.press('ControlOrMeta+Shift+z');
	await expect(paragraph).toHaveText('First draft');
});

test('a paragraph with $$…$$ renders display math when unfocused', async ({ page, request }) => {
	await openDocument(page, request);
	const editor = page.getByTestId('block-editor');
	const paragraph = editor.locator('[data-block-type="paragraph"] .editable').first();
	await paragraph.click();
	await paragraph.pressSequentially('Divergence: $$\\nabla \\cdot \\mathbf{F}$$');
	// Blur (focus another block) so the block switches from raw source to rich.
	await page.getByTestId('append-block').click();
	await expect(paragraph.locator('.katex-display')).toHaveCount(1);
	await expect(paragraph).toContainText('Divergence:');
});

test('image block embeds an external URL', async ({ page, request }) => {
	await openDocument(page, request);
	await page.getByTestId('append-block').click();
	await page.keyboard.type('/image');
	await expect(page.getByTestId('slash-menu')).toBeVisible();
	await page.keyboard.press('Enter');

	const block = page.getByTestId('image-block');
	await expect(block).toBeVisible();
	await block.getByTestId('image-url-input').fill('https://example.com/pic.png');
	await block.getByTestId('image-url-apply').click();
	await expect(block.getByTestId('image-external')).toHaveAttribute(
		'src',
		'https://example.com/pic.png'
	);
});

test('image block uploads a file and renders the served image', async ({ page, request }) => {
	await openDocument(page, request);
	await page.getByTestId('append-block').click();
	await page.keyboard.type('/image');
	await page.keyboard.press('Enter');

	const block = page.getByTestId('image-block');
	// A minimal valid 1x1 PNG (correct magic bytes so the backend accepts it).
	const png = Buffer.from(
		'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR4nGNgYGAAAAAEAAH2FzhVAAAAAElFTkSuQmCC',
		'base64'
	);
	await block
		.getByTestId('image-file-input')
		.setInputFiles({ name: 'dot.png', mimeType: 'image/png', buffer: png });

	// Uploaded images are served behind auth and rendered through <AuthImage>.
	await expect(block.getByTestId('auth-image')).toBeVisible();
});

test('embed block renders a YouTube player', async ({ page, request }) => {
	await openDocument(page, request);
	await page.getByTestId('append-block').click();
	await page.keyboard.type('/embed');
	await expect(page.getByTestId('slash-menu')).toBeVisible();
	await page.keyboard.press('Enter');

	const block = page.getByTestId('embed-block');
	await block.getByTestId('embed-url-input').fill('https://www.youtube.com/watch?v=dQw4w9WgXcQ');
	await block.getByTestId('embed-url-apply').click();
	await expect(block.getByTestId('embed-iframe')).toHaveAttribute(
		'src',
		'https://www.youtube.com/embed/dQw4w9WgXcQ'
	);
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
	await expect(table.locator('th .cell .editable')).toHaveCount(2);
	await table.getByTestId('add-column').click();
	await expect(table.locator('th .cell .editable')).toHaveCount(3);
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

test('whiteboard: shapes, mind-map child, arrow follows drag, persistence', async ({
	page,
	request
}) => {
	await openDocument(page, request);

	await page.getByTestId('append-block').click();
	await page.keyboard.type('/white');
	await page.keyboard.press('Enter');
	const board = page.getByTestId('whiteboard-block');
	await expect(board).toBeVisible();

	// Draw a rectangle, label it.
	await board.getByTestId('wb-tool-rect').click();
	await board.getByTestId('wb-canvas').click({ position: { x: 200, y: 120 } });
	await expect(board.getByTestId('wb-shape')).toHaveCount(1);
	await page.getByTestId('wb-label-input').fill('Root');
	await page.getByTestId('wb-label-input').press('Enter');

	// Mind map: add a connected child.
	await board.getByTestId('wb-shape').first().click();
	await board.getByTestId('wb-add-child').click();
	await expect(board.getByTestId('wb-shape')).toHaveCount(2);
	await expect(board.getByTestId('wb-arrow')).toHaveCount(1);

	// The bound arrow follows when the child moves.
	const arrow = board.getByTestId('wb-arrow');
	const y2Before = await arrow.getAttribute('y2');
	const child = board.getByTestId('wb-shape').nth(1);
	const box = (await child.boundingBox())!;
	await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
	await page.mouse.down();
	await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2 + 120, { steps: 5 });
	await page.mouse.up();
	const y2After = await arrow.getAttribute('y2');
	expect(Number(y2After)).toBeGreaterThan(Number(y2Before) + 100);

	// Scene survives a reload (CRDT log + data mirror).
	await page.reload();
	await page.getByTestId('whiteboard-block').waitFor();
	await expect(page.getByTestId('wb-shape')).toHaveCount(2);
	await expect(page.getByTestId('wb-arrow')).toHaveCount(1);
});

test('Backspace at the start of a block merges it into the previous one', async ({
	page,
	request
}) => {
	await openDocument(page, request);
	const editor = page.getByTestId('block-editor');

	// Two paragraphs: "hello " then "world".
	const first = editor.locator('[data-block-type="paragraph"] .editable').first();
	await first.click();
	await first.pressSequentially('hello ');
	await page.getByTestId('append-block').click();
	await page.keyboard.type('world');
	await expect(page.locator('[data-block-id]')).toHaveCount(2);

	// Caret is at the start of "world"; Backspace merges into "hello ".
	await page.keyboard.press('Home');
	await page.keyboard.press('Backspace');

	await expect(page.locator('[data-block-id]')).toHaveCount(1);
	await expect(editor.locator('.editable').first()).toHaveText('hello world');
});

test('inline $…$ math renders when a paragraph is not being edited', async ({
	page,
	request
}) => {
	await openDocument(page, request);
	const editor = page.getByTestId('block-editor');

	const paragraph = editor.locator('[data-block-type="paragraph"] .editable').first();
	await paragraph.click();
	await paragraph.pressSequentially('energy is $E = mc^2$ exactly');

	// Blur to another block: the inline math renders via KaTeX.
	await page.getByTestId('append-block').click();
	await expect(paragraph.locator('.katex')).toBeVisible();
	// Re-focusing restores the raw source for editing.
	await paragraph.click();
	await expect(paragraph).toHaveText(/\$E = mc\^2\$/);
});

test('a table cell renders inline emphasis when not being edited', async ({
	page,
	request
}) => {
	await openDocument(page, request);
	await page.getByTestId('append-block').click();
	await page.keyboard.type('/table');
	await expect(page.getByTestId('slash-menu')).toBeVisible();
	await page.keyboard.press('Enter');

	const firstCell = page.getByTestId('table-block').locator('.cell .editable').first();
	await firstCell.click();
	await firstCell.pressSequentially('**Bold**');
	// Blur elsewhere: the cell renders <strong>.
	await page.getByTestId('table-block').locator('.cell .editable').nth(1).click();
	await expect(firstCell.locator('strong')).toHaveText('Bold');
});

test('whiteboard: place an image and style a shape', async ({ page, request }) => {
	await openDocument(page, request);
	await page.getByTestId('append-block').click();
	await page.keyboard.type('/white');
	await page.keyboard.press('Enter');
	const board = page.getByTestId('whiteboard-block');
	await expect(board).toBeVisible();

	// Insert an image via the hidden file input (1x1 PNG data URL).
	const png =
		'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==';
	await board.getByTestId('wb-image-input').setInputFiles({
		name: 'dot.png',
		mimeType: 'image/png',
		buffer: Buffer.from(png, 'base64')
	});
	const image = board.locator('image');
	await expect(image).toHaveCount(1);
	// Embedded as a data URL so it travels in the scene.
	await expect(image).toHaveAttribute('href', /^data:image\/png/);

	// Draw a rectangle in empty space (clear of the image at 40–240px).
	await board.getByTestId('wb-tool-rect').click();
	await board.getByTestId('wb-canvas').click({ position: { x: 440, y: 300 } });
	await page.getByTestId('wb-label-input').fill('Box');
	await page.getByTestId('wb-label-input').press('Enter');

	// Select it and apply a fill.
	await board.locator('[data-kind="rect"]').first().click();
	await board.getByTestId('wb-fill').first().click();
	// The shape now carries an inline fill style.
	const rect = board.locator('[data-kind="rect"] rect');
	await expect(rect).toHaveAttribute('style', /fill:/);

	// Both survive a reload.
	await page.reload();
	await page.getByTestId('whiteboard-block').waitFor();
	await expect(page.getByTestId('whiteboard-block').locator('image')).toHaveCount(1);
	await expect(page.getByTestId('whiteboard-block').locator('[data-kind="rect"] rect')).toHaveAttribute(
		'style',
		/fill:/
	);
});

test('the block gutter stays reachable when the mouse sweeps toward it', async ({
	page,
	request
}) => {
	// Regression: the gutter (add/move/comment/delete) sat in a negative-margin
	// strip with a dead gap between it and the text, so moving the mouse over to
	// click a button lost :hover and the gutter vanished first.
	await openDocument(page, request);
	await page.getByTestId('append-block').click();
	await page.keyboard.type('a section');

	const row = page.locator('[data-block-id]').last();
	const body = row.locator('.body');
	const del = row.getByTestId('block-delete');

	await body.hover();
	await expect(del).toBeVisible();

	const btn = (await del.boundingBox())!;
	const bodyBox = (await body.boundingBox())!;
	const midY = btn.y + btn.height / 2;
	// The dead zone between the button's right edge and the text's left edge.
	const gapX = (btn.x + btn.width + bodyBox.x) / 2;

	await page.mouse.move(gapX, midY);
	await expect(del).toBeVisible(); // stays visible while crossing the gap
	await del.click(); // and is actually clickable
	await expect(page.locator('.editable', { hasText: 'a section' })).toHaveCount(0);
});

test('a mermaid diagram stays rendered while typing in another block', async ({
	page,
	request
}) => {
	// Regression: the render effect read block.id directly, subscribing it to the
	// whole block prop — which is re-created on every document mirror (any
	// keystroke). So typing elsewhere re-ran mermaid.render, blanking the diagram
	// (and jittering the layout).
	await openDocument(page, request);
	await page.getByTestId('append-block').click();
	await page.keyboard.type('/mermaid');
	await page.keyboard.press('Enter');
	const mm = page.getByTestId('mermaid-block').last();
	await mm.locator('textarea').fill('graph TD; A-->B; B-->C');
	const svg = mm.getByTestId('mermaid-render').locator('svg');
	await expect(svg).toBeVisible();
	const id = await svg.getAttribute('id');

	// Type in a separate block: the diagram must not re-render or vanish.
	await page.getByTestId('append-block').click();
	await page.keyboard.type('unrelated text');

	await expect(svg).toBeVisible();
	expect(await svg.getAttribute('id')).toBe(id); // same svg, not re-rendered
});
