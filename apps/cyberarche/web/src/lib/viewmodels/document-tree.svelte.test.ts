import { describe, expect, it, vi } from 'vitest';

import { createDocumentTree } from './document-tree.svelte';

const DOC = (id: string, title: string) => ({
	id,
	workspace_id: 'ws-1',
	title,
	parent_id: null,
	position: 0,
	created_by: 'alice',
	created_at: '2026-01-01T00:00:00Z',
	updated_at: '2026-01-01T00:00:00Z',
	trashed: false,
	teamspace_id: null
});

/** Resolves only when the test says so, to pin down interleaving. */
function deferred<T>() {
	let resolve!: (value: T) => void;
	const promise = new Promise<T>((r) => (resolve = r));
	return { promise, resolve };
}

describe('document tree ViewModel', () => {
	it('a document created while the tree is loading is not lost', async () => {
		// Regression: open() replaced `roots` with a list fetched BEFORE the new
		// document existed, so the document vanished from the sidebar and the
		// later rename() could not find its node — the title never appeared.
		const listing = deferred<unknown>();
		vi.stubGlobal(
			'fetch',
			vi.fn(async (url: string, init?: RequestInit) => {
				const method = init?.method ?? 'GET';
				if (method === 'POST' && url === '/api/v1/documents') {
					return { ok: true, status: 200, json: async () => DOC('new-1', 'Untitled') };
				}
				// GET /api/v1/workspaces/ws-1/documents — the slow initial listing.
				return { ok: true, status: 200, json: async () => await listing.promise };
			}) as unknown as typeof fetch
		);

		const tree = createDocumentTree();
		const opening = tree.open('ws-1'); // in flight...
		const creating = tree.create(); // ...user hits "New document"

		listing.resolve([]); // the listing lands, and it predates the new doc
		await opening;
		await creating;

		expect(tree.roots.map((n) => n.document.id)).toEqual(['new-1']);
		expect(tree.find('new-1')).not.toBeNull();
	});

	it('rename updates the node the sidebar renders', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async (url: string, init?: RequestInit) => {
				const method = init?.method ?? 'GET';
				if (method === 'GET') return { ok: true, status: 200, json: async () => [DOC('d-1', 'Untitled')] };
				return { ok: true, status: 200, json: async () => DOC('d-1', 'Retrieval Pipeline RFC') };
			}) as unknown as typeof fetch
		);

		const tree = createDocumentTree();
		await tree.open('ws-1');
		await tree.rename('d-1', 'Retrieval Pipeline RFC');

		expect(tree.roots[0].document.title).toBe('Retrieval Pipeline RFC');
	});

	it('purge drops a document from the trash list', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async (url: string, init?: RequestInit) => {
				const method = init?.method ?? 'GET';
				if (method === 'GET') return { ok: true, status: 200, json: async () => [DOC('d-1', 'Doomed')] };
				if (method === 'DELETE' && url === '/api/v1/documents/d-1')
					return { ok: true, status: 200, json: async () => ({ ...DOC('d-1', 'Doomed'), trashed: true }) };
				// DELETE /api/v1/documents/d-1/trash  -> purge
				if (method === 'DELETE' && url.endsWith('/trash'))
					return { ok: true, status: 200, json: async () => ({ purged: ['d-1'] }) };
				throw new Error(`unrouted: ${method} ${url}`);
			}) as unknown as typeof fetch
		);

		const tree = createDocumentTree();
		await tree.open('ws-1');
		await tree.moveToTrash('d-1');
		expect(tree.trash.map((d) => d.id)).toEqual(['d-1']);

		await tree.purge('d-1');
		expect(tree.trash).toEqual([]);
		expect(tree.roots).toEqual([]);
	});
});
