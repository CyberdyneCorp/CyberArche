import { expect, test, type Page } from '@playwright/test';

import { loadSession, type Session } from './session';

/** The four UI/UX gaps reported from the deployed product:
 *  1. no block delete control     2. agent cannot edit the document
 *  3. no insert-as-block on answers   4. no workspace switcher / Teamspaces
 */

const EMAIL = process.env.CYBERARCHE_IT_EMAIL ?? '';
const PASSWORD = process.env.CYBERARCHE_IT_PASSWORD ?? '';
const API = 'http://127.0.0.1:8123';

test.skip(!EMAIL || !PASSWORD, 'CYBERARCHE_IT_EMAIL / _PASSWORD not configured');

let session: Session;
let workspaceId: string;

test.beforeAll(async ({ request }) => {
	session = loadSession();
	const workspace = await (
		await request.post(`${API}/api/v1/workspaces`, {
			data: { name: 'Teamspace E2E' },
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
		await request.post(`${API}/api/v1/documents`, {
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
	return document.id;
}

test('a block can be deleted from its controls, and undone', async ({ page, request }) => {
	await openDocument(page, request);

	// Two blocks: the seeded paragraph plus one appended.
	await page.getByTestId('append-block').click();
	await page.keyboard.type('delete me');
	await expect(page.locator('[data-block-id]')).toHaveCount(2);

	const row = page.getByTestId('block-editor').locator('.row').last();
	await row.hover();
	await row.getByTestId('block-delete').click();
	await expect(page.locator('[data-block-id]')).toHaveCount(1);
	await expect(page.locator('.editable', { hasText: 'delete me' })).toHaveCount(0);

	// Undoable (block-editor spec).
	await page.keyboard.press('ControlOrMeta+z');
	await expect(page.locator('[data-block-id]')).toHaveCount(2);
});

test('workspace switcher lists workspaces and creates a new one', async ({
	page,
	request
}) => {
	await openDocument(page, request);

	await page.getByTestId('workspace-switcher').click();
	const menu = page.getByTestId('workspace-menu');
	await expect(menu).toBeVisible();
	await expect(menu.getByTestId('workspace-option').first()).toBeVisible();

	await menu.getByTestId('new-workspace').click();
	await page.getByTestId('new-workspace-name').fill('Switched WS');
	await page.getByTestId('new-workspace-create').click();

	await page.waitForURL(/\/w\/(?!new)/);
	await expect(page.getByTestId('workspace-name')).toHaveText('Switched WS');
});

test('create a teamspace, add a page to it, and favourite a document', async ({
	page,
	request
}) => {
	await openDocument(page, request);

	// Teamspaces section starts empty.
	await expect(page.getByTestId('no-teamspaces')).toBeVisible();

	await page.getByTestId('new-teamspace').click();
	await page.getByTestId('teamspace-name').fill('Tessera');
	await page.getByTestId('teamspace-name').press('Enter');
	await expect(page.getByTestId('teamspace-name-label')).toHaveText('Tessera');

	// Add a page inside the teamspace -> it lands under it, not the tree root.
	const teamspaceRow = page.getByTestId('teamspace-row');
	await teamspaceRow.hover();
	await teamspaceRow.getByTestId('teamspace-add-page').click();
	await page.waitForURL(/\/d\//);
	await expect(page.getByTestId('teamspace-doc')).toHaveCount(1);

	// Favourite a workspace-level document -> it appears under Favorites.
	const treeRow = page.getByTestId('document-tree').locator('.item').first();
	await treeRow.hover();
	await treeRow.getByTestId('favorite-toggle').click();
	await expect(page.getByTestId('favorite-doc')).toHaveCount(1);
});

test('agent answers offer Insert / Replace / Copy', async ({ page, request }) => {
	// No LLM key needed: the panel's actions come from the answer's blocks, so
	// stub the ask endpoint to keep this deterministic and fast.
	await page.route('**/agent/ask', (route) =>
		route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify({
				answer: 'CRDTs converge without a central authority.',
				blocks: [
					{ id: 'a1', type: 'paragraph', data: { text: 'CRDTs converge.' } }
				]
			})
		})
	);
	await openDocument(page, request);

	await page.getByTestId('agent-toggle').click();
	await page.getByTestId('agent-prompt').fill('What is a CRDT?');
	await page.getByTestId('agent-prompt').press('Enter');

	// Every conversational answer carries the three actions (ai-agent spec).
	await expect(page.getByTestId('insert-as-block')).toBeVisible();
	await expect(page.getByTestId('replace-selection')).toBeVisible();
	await expect(page.getByTestId('copy-answer')).toBeVisible();

	const before = await page.locator('[data-block-id]').count();
	await page.getByTestId('insert-as-block').click();
	await expect(page.getByTestId('insert-as-block')).toHaveText(/Inserted/);
	await expect
		.poll(async () => page.locator('[data-block-id]').count(), { timeout: 10_000 })
		.toBeGreaterThan(before);
});

test('the sidebar surfaces documents shared with me', async ({ page, request }) => {
	// A true end-to-end needs a SECOND identity (a document granted to us in a
	// workspace we don't belong to) and the suite has one test account. The
	// grant semantics — inherited access excluded, trashed excluded, per-user
	// scoping — are covered by tests/test_sharing.py against the real use case
	// and by the Postgres contract test. Here we pin the rendering contract.
	await page.route('**/api/v1/shared', (route) =>
		route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify([
				{
					id: 'granted-1',
					workspace_id: 'someone-elses-ws',
					title: 'Design Review (shared)',
					parent_id: null,
					position: 0,
					created_by: 'someone-else',
					created_at: '2026-01-01T00:00:00Z',
					updated_at: '2026-01-01T00:00:00Z',
					trashed: false,
					teamspace_id: null
				}
			])
		})
	);
	await openDocument(page, request);

	const shared = page.getByTestId('shared-doc');
	await expect(shared).toHaveCount(1);
	await expect(shared).toContainText('Design Review (shared)');

	// It lives in its own section, never in the workspace tree.
	await expect(page.getByTestId('document-tree')).not.toContainText('shared');
});

test('a trashed document can be permanently deleted', async ({ page, request }) => {
	await openDocument(page, request);

	// Create a second document so we can trash one without emptying the tree.
	const doomed = await (
		await request.post(`${API}/api/v1/documents`, {
			data: { workspace_id: workspaceId, title: 'Doomed' },
			headers: { Authorization: `Bearer ${session.access}` }
		})
	).json();
	await page.goto(`/w/${workspaceId}/d/${doomed.id}`);
	await page.getByTestId('block-editor').waitFor();

	// Trash it from the tree.
	const row = page
		.getByTestId('document-tree')
		.locator('.item')
		.filter({ hasText: 'Doomed' })
		.first();
	await row.hover();
	await row.getByLabel('Move to trash').click();
	await expect(page.getByTestId('trash-doc').filter({ hasText: 'Doomed' })).toHaveCount(1);

	// Permanently delete it — the in-app confirm dialog must be accepted.
	await page
		.getByTestId('trash-doc')
		.filter({ hasText: 'Doomed' })
		.getByTestId('trash-purge')
		.click();
	await expect(page.getByTestId('confirm-dialog')).toBeVisible();
	await page.getByTestId('dialog-confirm').click();
	await expect(page.getByTestId('trash-doc').filter({ hasText: 'Doomed' })).toHaveCount(0);

	// The backend agrees it is gone: it cannot be restored.
	const restore = await request.post(`${API}/api/v1/documents/${doomed.id}/restore`, {
		headers: { Authorization: `Bearer ${session.access}` }
	});
	expect(restore.status()).toBe(404);
});

test('inserting an answer with math adds a rendered latex block locally', async ({
	page,
	request
}) => {
	// The backend parses answers into typed blocks; stub ask to return a latex
	// block so this is deterministic. Insert applies to the local editor doc,
	// so it must appear without relying on a server broadcast.
	await page.route('**/agent/ask', (route) =>
		route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify({
				answer: 'The identity is $$e^{i\\pi}+1=0$$.',
				blocks: [
					{ id: 'm1', type: 'paragraph', data: { text: 'The identity is' } },
					{ id: 'm2', type: 'latex', data: { source: 'e^{i\\pi}+1=0' } }
				]
			})
		})
	);
	await openDocument(page, request);

	await page.getByTestId('agent-toggle').click();
	await page.getByTestId('agent-prompt').fill('Euler?');
	await page.getByTestId('agent-prompt').press('Enter');
	await page.getByTestId('insert-as-block').click();

	// A real latex block appears and KaTeX renders it — not raw source text.
	const latex = page.getByTestId('block-editor').locator('[data-block-type="latex"]');
	await expect(latex).toHaveCount(1);
	await expect(latex.locator('.katex')).toBeVisible();
});

test('folders live under a teamspace and the Private section holds loose docs', async ({
	page,
	request
}) => {
	await openDocument(page, request);

	// A teamspace to hold a folder.
	await page.getByTestId('new-teamspace').click();
	await page.getByTestId('teamspace-name').fill('Eng');
	await page.getByTestId('teamspace-name').press('Enter');
	await expect(
		page.getByTestId('teamspace-name-label').filter({ hasText: 'Eng' })
	).toHaveCount(1);

	// Create a folder in the teamspace (in-app prompt dialog).
	const row = page.getByTestId('teamspace-row').filter({ hasText: 'Eng' });
	await row.hover();
	await row.getByTestId('teamspace-add-folder').click();
	await page.getByTestId('dialog-input').fill('Specs');
	await page.getByTestId('dialog-confirm').click();
	await expect(page.getByTestId('folder-name').filter({ hasText: 'Specs' })).toHaveCount(1);

	// Add a page inside the folder -> it lands under the folder (not the tree root).
	const folder = page.getByTestId('folder-row').filter({ hasText: 'Specs' });
	await folder.hover();
	await folder.getByTestId('folder-add-page').click();
	await page.waitForURL(/\/d\//);
	// Expand the folder and see the page.
	await folder.getByLabel('Expand').click();
	await expect(page.getByTestId('folder-doc')).toHaveCount(1);

	// The Private section exists (loose docs live here, not a global "Documents").
	await expect(page.getByRole('heading', { name: 'Private' })).toBeVisible();
});

test('drag a private doc into a teamspace, then star and trash it there', async ({
	page,
	request
}) => {
	await openDocument(page, request);
	// A private doc to move.
	const doc = await (
		await request.post(`${API}/api/v1/documents`, {
			data: { workspace_id: workspaceId, title: 'Draggable' },
			headers: { Authorization: `Bearer ${session.access}` }
		})
	).json();
	await page.goto(`/w/${workspaceId}/d/${doc.id}`);
	await page.getByTestId('block-editor').waitFor();

	// A teamspace to drop it into.
	await page.getByTestId('new-teamspace').click();
	await page.getByTestId('teamspace-name').fill('Dropzone');
	await page.getByTestId('teamspace-name').press('Enter');
	const teamspace = page.getByTestId('teamspace-row').filter({ hasText: 'Dropzone' });
	await expect(teamspace).toHaveCount(1);

	// Drag the private doc (a tree item) onto the teamspace.
	const source = page
		.getByTestId('document-tree')
		.locator('.item')
		.filter({ hasText: 'Draggable' })
		.first();
	await source.dragTo(teamspace);

	// It now lives under the teamspace, not Private. The teamspace is already
	// expanded (a freshly created teamspace opens) and stays open across the move.
	const inTeamspace = page.getByTestId('teamspace-doc').filter({ hasText: 'Draggable' });
	await expect(inTeamspace).toHaveCount(1);

	// Star it -> appears under Favorites.
	await inTeamspace.hover();
	await inTeamspace.locator('..').getByTestId('doc-star').click();
	await expect(page.getByTestId('favorite-doc').filter({ hasText: 'Draggable' })).toHaveCount(1);

	// Trash it -> gone from the teamspace.
	await inTeamspace.hover();
	await inTeamspace.locator('..').getByTestId('doc-trash').click();
	await expect(page.getByTestId('teamspace-doc').filter({ hasText: 'Draggable' })).toHaveCount(0);
});

test('dragging a doc into a folder places it once and keeps the teamspace open', async ({
	page,
	request
}) => {
	await openDocument(page, request);
	const doc = await (
		await request.post(`${API}/api/v1/documents`, {
			data: { workspace_id: workspaceId, title: 'ToFolder' },
			headers: { Authorization: `Bearer ${session.access}` }
		})
	).json();
	await page.goto(`/w/${workspaceId}/d/${doc.id}`);
	await page.getByTestId('block-editor').waitFor();

	// A teamspace with a folder, both expanded.
	await page.getByTestId('new-teamspace').click();
	await page.getByTestId('teamspace-name').fill('Docs');
	await page.getByTestId('teamspace-name').press('Enter');
	const teamspace = page.getByTestId('teamspace-row').filter({ hasText: 'Docs' });
	await teamspace.hover();
	await teamspace.getByTestId('teamspace-add-folder').click();
	await page.getByTestId('dialog-input').fill('Bucket');
	await page.getByTestId('dialog-confirm').click();
	const folder = page.getByTestId('folder-row').filter({ hasText: 'Bucket' });
	await expect(folder).toHaveCount(1);
	await folder.getByLabel('Expand').click();

	// Drag the private doc onto the folder.
	const source = page
		.getByTestId('document-tree')
		.locator('.item')
		.filter({ hasText: 'ToFolder' })
		.first();
	await source.dragTo(folder);

	// Regression: it lands under the folder exactly once — not also as a loose
	// teamspace doc — and the teamspace does not collapse (the folder is still shown).
	await expect(page.getByTestId('folder-doc').filter({ hasText: 'ToFolder' })).toHaveCount(1);
	await expect(page.getByTestId('teamspace-doc').filter({ hasText: 'ToFolder' })).toHaveCount(0);
	await expect(folder).toHaveCount(1);
});

test('delete a folder then its teamspace from the sidebar, moving docs to Trash', async ({
	page,
	request
}) => {
	await openDocument(page, request);

	// A teamspace, a folder in it, and a page inside the folder.
	await page.getByTestId('new-teamspace').click();
	await page.getByTestId('teamspace-name').fill('Doomed');
	await page.getByTestId('teamspace-name').press('Enter');
	const teamspace = page.getByTestId('teamspace-row').filter({ hasText: 'Doomed' });
	await teamspace.hover();
	await teamspace.getByTestId('teamspace-add-folder').click();
	await page.getByTestId('dialog-input').fill('Trashme');
	await page.getByTestId('dialog-confirm').click();
	const folder = page.getByTestId('folder-row').filter({ hasText: 'Trashme' });
	await expect(folder).toHaveCount(1);
	// We're already on a /d/ page (openDocument navigated there), so wait for the
	// URL to change to the newly created folder page rather than matching /d/.
	const prevUrl = page.url();
	await folder.hover();
	await folder.getByTestId('folder-add-page').click();
	await expect.poll(() => page.url()).not.toBe(prevUrl);
	const folderedDocId = page.url().split('/d/')[1];

	// Delete the folder via its kebab (⋯) menu -> in-app confirm dialog.
	await folder.hover();
	await folder.getByTestId('folder-menu').click();
	await expect(page.getByTestId('context-menu')).toBeVisible();
	await page.getByTestId('folder-delete').click();
	await expect(page.getByTestId('confirm-dialog')).toBeVisible();
	await page.getByTestId('dialog-confirm').click();

	// Toast confirms it and the folder is gone.
	await expect(page.getByTestId('toast').filter({ hasText: 'Deleted' })).toHaveCount(1);
	await expect(page.getByTestId('folder-row').filter({ hasText: 'Trashme' })).toHaveCount(0);
	// The folder's page is now in the workspace trash (recoverable).
	const trash = await (
		await request.get(`${API}/api/v1/workspaces/${workspaceId}/trash`, {
			headers: { Authorization: `Bearer ${session.access}` }
		})
	).json();
	expect(trash.map((d: { id: string }) => d.id)).toContain(folderedDocId);

	// Delete the (now empty) teamspace via right-click context menu.
	await teamspace.click({ button: 'right' });
	await expect(page.getByTestId('context-menu')).toBeVisible();
	await page.getByTestId('teamspace-delete').click();
	await expect(page.getByTestId('confirm-dialog')).toBeVisible();
	await page.getByTestId('dialog-confirm').click();
	await expect(page.getByTestId('teamspace-row').filter({ hasText: 'Doomed' })).toHaveCount(0);
});

test('restore all, then empty the trash from the sidebar', async ({ page, request }) => {
	await openDocument(page, request);
	const headers = { Authorization: `Bearer ${session.access}` };
	async function trashNew(title: string) {
		const d = await (
			await request.post(`${API}/api/v1/documents`, {
				data: { workspace_id: workspaceId, title },
				headers
			})
		).json();
		await request.delete(`${API}/api/v1/documents/${d.id}`, { headers });
	}

	await trashNew('Bulk A');
	await trashNew('Bulk B');
	// Reload so the sidebar loads the trash from the server.
	await page.reload();
	await page.getByTestId('block-editor').waitFor();
	await expect(page.getByTestId('trash-doc').filter({ hasText: 'Bulk A' })).toHaveCount(1);
	await expect(page.getByTestId('trash-doc').filter({ hasText: 'Bulk B' })).toHaveCount(1);

	// Restore all empties the trash.
	await page.getByTestId('trash-restore-all').click();
	await expect(page.getByTestId('trash-doc')).toHaveCount(0);

	// Trash one more, then Delete all — which asks for confirmation first.
	await trashNew('Bulk C');
	await page.reload();
	await page.getByTestId('block-editor').waitFor();
	await expect(page.getByTestId('trash-doc').filter({ hasText: 'Bulk C' })).toHaveCount(1);
	await page.getByTestId('trash-empty').click();
	await expect(page.getByTestId('confirm-dialog')).toBeVisible();
	await page.getByTestId('dialog-confirm').click();
	await expect(page.getByTestId('trash-doc')).toHaveCount(0);
});

test('wikilink resolves, navigates, and shows as a backlink on the target', async ({
	page,
	request
}) => {
	const headers = { Authorization: `Bearer ${session.access}` };
	const TARGET = `WikiTarget ${Date.now()}`;
	await request.post(`${API}/api/v1/documents`, {
		data: { workspace_id: workspaceId, title: TARGET },
		headers
	});

	await openDocument(page, request); // a fresh source doc, workspace index loads
	const paragraph = page
		.getByTestId('block-editor')
		.locator('[data-block-type="paragraph"] .editable')
		.first();
	await paragraph.click();
	await paragraph.pressSequentially(`See [[${TARGET}]] now`);
	await page.getByTestId('append-block').click(); // blur -> rich render

	// The wikilink resolves to a clickable link (retries until the index loads).
	const link = paragraph.locator('a.wikilink', { hasText: TARGET });
	await expect(link).toHaveCount(1);
	await expect(page.getByTestId('sync-status')).toHaveText('Synced'); // edit persisted

	await link.click();
	await expect(page.getByTestId('doc-title')).toHaveValue(TARGET);
	// The source document appears in the target's backlinks.
	await expect(page.getByTestId('backlink')).toHaveCount(1);
});

test('Cmd+K palette jumps to a document', async ({ page, request }) => {
	const headers = { Authorization: `Bearer ${session.access}` };
	const TARGET = `PaletteTarget ${Date.now()}`;
	await request.post(`${API}/api/v1/documents`, {
		data: { workspace_id: workspaceId, title: TARGET },
		headers
	});

	await openDocument(page, request);
	await page.keyboard.press('ControlOrMeta+k');
	await expect(page.getByTestId('command-palette')).toBeVisible();
	await page.getByTestId('palette-input').fill(TARGET);
	await page.getByTestId('palette-result').first().click();
	await expect(page.getByTestId('doc-title')).toHaveValue(TARGET);
});
