import { describe, expect, it, vi } from 'vitest';

import { docTitles } from './doc-titles';
import { createDocumentTree } from './document-tree.svelte';

const DOC = (id: string, title: string, parent_id: string | null = null) => ({
	id,
	workspace_id: 'ws-1',
	title,
	parent_id,
	position: 0,
	created_by: 'alice',
	created_at: '2026-01-01T00:00:00Z',
	updated_at: '2026-01-01T00:00:00Z',
	trashed: false,
	teamspace_id: null
});

/** Routes fetch by URL+method so the VM's real request shapes are exercised. */
function routedFetch(routes: Record<string, unknown>) {
	return vi.fn(async (url: string, init?: RequestInit) => {
		const key = `${init?.method ?? 'GET'} ${url}`;
		const body = routes[key];
		if (body === undefined) throw new Error(`unrouted: ${key}`);
		return { ok: true, status: 200, json: async () => body };
	}) as unknown as typeof fetch;
}

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
				if (method === 'GET' && url.endsWith('/trash'))
					return { ok: true, status: 200, json: async () => [] };
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

	it('open() loads the trash from the server', async () => {
		// So a document trashed elsewhere (e.g. by deleting its teamspace/folder)
		// shows in the Trash section after a refresh, not only within this session.
		vi.stubGlobal(
			'fetch',
			vi.fn(async (url: string, init?: RequestInit) => {
				const method = init?.method ?? 'GET';
				if (method === 'GET' && url.endsWith('/trash'))
					return { ok: true, status: 200, json: async () => [DOC('t-1', 'Gone')] };
				return { ok: true, status: 200, json: async () => [DOC('d-1', 'Live')] };
			}) as unknown as typeof fetch
		);

		const tree = createDocumentTree();
		await tree.open('ws-1');

		expect(tree.roots.map((n) => n.document.id)).toEqual(['d-1']);
		expect(tree.trash.map((d) => d.id)).toEqual(['t-1']);
	});

	it('toggle expands lazily, loading children exactly once', async () => {
		const fetchMock = routedFetch({
			'GET /api/v1/documents?workspace_id=ws-1': [DOC('d-1', 'Parent')],
			'GET /api/v1/workspaces/ws-1/trash': [],
			'GET /api/v1/documents?workspace_id=ws-1&parent_id=d-1': [DOC('c-1', 'Child', 'd-1')]
		});
		vi.stubGlobal('fetch', fetchMock);

		const tree = createDocumentTree();
		await tree.open('ws-1');
		expect(tree.workspaceId).toBe('ws-1');

		await tree.toggle('d-1');
		expect(tree.roots[0].expanded).toBe(true);
		expect(tree.roots[0].children.map((n) => n.document.id)).toEqual(['c-1']);
		expect(tree.find('c-1')).not.toBeNull(); // findNode recurses into children

		await tree.toggle('d-1'); // collapse
		expect(tree.roots[0].expanded).toBe(false);
		await tree.toggle('d-1'); // re-expand: children already loaded
		expect(tree.roots[0].expanded).toBe(true);

		const childListings = (fetchMock as ReturnType<typeof vi.fn>).mock.calls.filter(
			([url]: [string]) => String(url).includes('parent_id=d-1')
		);
		expect(childListings).toHaveLength(1);

		await tree.toggle('ghost'); // unknown id: a no-op
		expect(tree.find('ghost')).toBeNull();
	});

	it('loadChildren on an unknown node is a no-op', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/documents?workspace_id=ws-1': [],
				'GET /api/v1/workspaces/ws-1/trash': []
			})
		);
		const tree = createDocumentTree();
		await tree.open('ws-1');
		await tree.loadChildren('ghost'); // must not hit an unrouted URL
	});

	it('create refuses without an open workspace', async () => {
		const tree = createDocumentTree();
		await expect(tree.create()).rejects.toThrow(/no workspace open/);
	});

	it('create nests under its parent and expands it', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/documents?workspace_id=ws-1': [DOC('d-1', 'Parent')],
				'GET /api/v1/workspaces/ws-1/trash': [],
				'POST /api/v1/documents': DOC('c-1', 'Child', 'd-1')
			})
		);
		const tree = createDocumentTree();
		await tree.open('ws-1');

		const created = await tree.create('Child', 'd-1');

		expect(created.id).toBe('c-1');
		expect(tree.roots[0].expanded).toBe(true);
		expect(tree.roots[0].childrenLoaded).toBe(true); // no extra fetch needed
		expect(tree.roots[0].children.map((n) => n.document.id)).toEqual(['c-1']);
	});

	it('create under an unknown parent still returns the document', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/documents?workspace_id=ws-1': [],
				'GET /api/v1/workspaces/ws-1/trash': [],
				'POST /api/v1/documents': DOC('c-1', 'Orphan', 'ghost')
			})
		);
		const tree = createDocumentTree();
		await tree.open('ws-1');

		const created = await tree.create('Orphan', 'ghost');
		expect(created.id).toBe('c-1');
		expect(tree.roots).toEqual([]); // the tree shows nothing for it
	});

	it('a teamspace document is not added to the private tree', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/documents?workspace_id=ws-1': [],
				'GET /api/v1/workspaces/ws-1/trash': [],
				'POST /api/v1/documents': { ...DOC('t-doc', 'Team doc'), teamspace_id: 'ts-1' }
			})
		);
		const tree = createDocumentTree();
		await tree.open('ws-1');

		const created = await tree.create('Team doc', undefined, 'ts-1');
		expect(created.id).toBe('t-doc');
		expect(tree.roots).toEqual([]); // listed under its teamspace instead
	});

	it('rename publishes the live title even when the node is not in this tree', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/documents?workspace_id=ws-1': [],
				'GET /api/v1/workspaces/ws-1/trash': [],
				'PATCH /api/v1/documents/ts-doc/title': { ...DOC('ts-doc', 'New name'), teamspace_id: 'ts-1' }
			})
		);
		const tree = createDocumentTree();
		await tree.open('ws-1');

		await tree.rename('ts-doc', 'New name');

		// e.g. a teamspace document: its sidebar copy must still update.
		expect(docTitles.titleOf({ id: 'ts-doc', title: 'Stale' })).toBe('New name');
	});

	it('moveToTrash removes a nested child from its parent', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/documents?workspace_id=ws-1': [DOC('d-1', 'Parent')],
				'GET /api/v1/workspaces/ws-1/trash': [],
				'GET /api/v1/documents?workspace_id=ws-1&parent_id=d-1': [DOC('c-1', 'Child', 'd-1')],
				'DELETE /api/v1/documents/c-1': { ...DOC('c-1', 'Child', 'd-1'), trashed: true }
			})
		);
		const tree = createDocumentTree();
		await tree.open('ws-1');
		await tree.toggle('d-1');
		expect(tree.find('c-1')).not.toBeNull();

		await tree.moveToTrash('c-1');

		expect(tree.find('c-1')).toBeNull();
		expect(tree.roots[0].children).toEqual([]);
		expect(tree.trash.map((d) => d.id)).toEqual(['c-1']);
	});

	it('restore puts a root document back among the roots', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/documents?workspace_id=ws-1': [],
				'GET /api/v1/workspaces/ws-1/trash': [DOC('d-1', 'Trashed')],
				'POST /api/v1/documents/d-1/restore': DOC('d-1', 'Trashed')
			})
		);
		const tree = createDocumentTree();
		await tree.open('ws-1');

		const restored = await tree.restore('d-1');

		expect(restored.id).toBe('d-1');
		expect(tree.trash).toEqual([]);
		expect(tree.roots.map((n) => n.document.id)).toEqual(['d-1']);
	});

	it('restore reloads the parent children only when they were loaded', async () => {
		let children: unknown[] = [];
		vi.stubGlobal(
			'fetch',
			vi.fn(async (url: string, init?: RequestInit) => {
				const key = `${init?.method ?? 'GET'} ${url}`;
				const routes: Record<string, unknown> = {
					'GET /api/v1/documents?workspace_id=ws-1': [DOC('d-1', 'Parent')],
					'GET /api/v1/workspaces/ws-1/trash': [DOC('c-1', 'Child', 'd-1')],
					'GET /api/v1/documents?workspace_id=ws-1&parent_id=d-1': children,
					'POST /api/v1/documents/c-1/restore': DOC('c-1', 'Child', 'd-1')
				};
				if (!(key in routes)) throw new Error(`unrouted: ${key}`);
				return { ok: true, status: 200, json: async () => routes[key] };
			}) as unknown as typeof fetch
		);
		const tree = createDocumentTree();
		await tree.open('ws-1');
		await tree.toggle('d-1'); // children loaded (empty)

		children = [DOC('c-1', 'Child', 'd-1')];
		await tree.restore('c-1');

		expect(tree.trash).toEqual([]);
		expect(tree.roots[0].children.map((n) => n.document.id)).toEqual(['c-1']);
	});

	it('restore into a collapsed (unloaded) parent defers loading', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/documents?workspace_id=ws-1': [DOC('d-1', 'Parent')],
				'GET /api/v1/workspaces/ws-1/trash': [DOC('c-1', 'Child', 'd-1')],
				'POST /api/v1/documents/c-1/restore': DOC('c-1', 'Child', 'd-1')
			})
		);
		const tree = createDocumentTree();
		await tree.open('ws-1');

		await tree.restore('c-1'); // no child-listing route: must not fetch

		expect(tree.trash).toEqual([]);
		expect(tree.roots[0].children).toEqual([]); // loads on expand instead
	});

	it('restore into an unknown parent leaves the tree unchanged', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/documents?workspace_id=ws-1': [],
				'GET /api/v1/workspaces/ws-1/trash': [DOC('c-1', 'Child', 'ghost')],
				'POST /api/v1/documents/c-1/restore': DOC('c-1', 'Child', 'ghost')
			})
		);
		const tree = createDocumentTree();
		await tree.open('ws-1');

		await tree.restore('c-1');

		expect(tree.trash).toEqual([]);
		expect(tree.roots).toEqual([]);
	});
});
