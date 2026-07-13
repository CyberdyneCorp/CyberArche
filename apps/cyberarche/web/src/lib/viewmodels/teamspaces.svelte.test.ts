import { beforeEach, describe, expect, it, vi } from 'vitest';

import { createTeamspaces } from './teamspaces.svelte';

const TEAMSPACE = {
	id: 'ts-1',
	workspace_id: 'ws-1',
	name: 'Tessera',
	icon: 'T',
	created_at: '2026-01-01T00:00:00Z'
};

const DOC = (id: string, teamspace_id: string | null = null) => ({
	id,
	workspace_id: 'ws-1',
	title: `Doc ${id}`,
	parent_id: null,
	position: 0,
	created_by: 'alice',
	created_at: '2026-01-01T00:00:00Z',
	updated_at: '2026-01-01T00:00:00Z',
	trashed: false,
	teamspace_id
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

describe('teamspaces ViewModel', () => {
	beforeEach(() => vi.restoreAllMocks());

	it('loads teamspaces and favourites, lazily expanding documents', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/workspaces/ws-1/teamspaces': [TEAMSPACE],
				'GET /api/v1/favorites': [DOC('fav-1')],
				'GET /api/v1/shared': [],
				'GET /api/v1/workspaces/ws-1/private': [],
				'GET /api/v1/workspaces/ws-1/folders': [],
				'GET /api/v1/teamspaces/ts-1/documents': [DOC('d-1', 'ts-1')]
			})
		);
		const vm = createTeamspaces('ws-1');
		await vm.load();

		expect(vm.nodes).toHaveLength(1);
		expect(vm.nodes[0].expanded).toBe(false);
		expect(vm.nodes[0].documents).toEqual([]); // not fetched until expanded
		expect(vm.favorites.map((d) => d.id)).toEqual(['fav-1']);

		await vm.toggle('ts-1');
		expect(vm.nodes[0].expanded).toBe(true);
		expect(vm.nodes[0].documents.map((d) => d.id)).toEqual(['d-1']);
	});

	it('isFavorite reflects the loaded favourites', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/workspaces/ws-1/teamspaces': [],
				'GET /api/v1/favorites': [DOC('fav-1')],
				'GET /api/v1/shared': [],
				'GET /api/v1/workspaces/ws-1/private': [],
				'GET /api/v1/workspaces/ws-1/folders': []
			})
		);
		const vm = createTeamspaces('ws-1');
		await vm.load();

		expect(vm.isFavorite('fav-1')).toBe(true);
		expect(vm.isFavorite('other')).toBe(false);
	});

	it('toggleFavorite adds then removes', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/workspaces/ws-1/teamspaces': [],
				'GET /api/v1/favorites': [],
				'GET /api/v1/shared': [],
				'GET /api/v1/workspaces/ws-1/private': [],
				'GET /api/v1/workspaces/ws-1/folders': [],
				'POST /api/v1/favorites': null,
				'DELETE /api/v1/favorites/d-1': null
			})
		);
		const vm = createTeamspaces('ws-1');
		await vm.load();
		const doc = DOC('d-1');

		await vm.toggleFavorite(doc);
		expect(vm.isFavorite('d-1')).toBe(true);

		await vm.toggleFavorite(doc);
		expect(vm.isFavorite('d-1')).toBe(false);
	});

	it('create appends an expanded teamspace', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/workspaces/ws-1/teamspaces': [],
				'GET /api/v1/favorites': [],
				'GET /api/v1/shared': [],
				'GET /api/v1/workspaces/ws-1/private': [],
				'GET /api/v1/workspaces/ws-1/folders': [],
				'POST /api/v1/workspaces/ws-1/teamspaces': TEAMSPACE
			})
		);
		const vm = createTeamspaces('ws-1');
		await vm.load();

		const created = await vm.create('Tessera');

		expect(created?.id).toBe('ts-1');
		expect(vm.nodes[0].expanded).toBe(true);
		expect(vm.nodes[0].loaded).toBe(true); // no extra fetch needed
	});

	it('surfaces a create failure without adding a node', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async (url: string, init?: RequestInit) => {
				if ((init?.method ?? 'GET') === 'POST') {
					return { ok: false, status: 403, json: async () => ({ detail: 'nope' }) };
				}
				return { ok: true, status: 200, json: async () => [] };
			}) as unknown as typeof fetch
		);
		const vm = createTeamspaces('ws-1');
		await vm.load();

		expect(await vm.create('Denied')).toBeNull();
		expect(vm.nodes).toHaveLength(0);
		expect(vm.error).toMatch(/403/);
	});

	it('shared-with-me is exposed separately from the document tree', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/workspaces/ws-1/teamspaces': [],
				'GET /api/v1/favorites': [],
				'GET /api/v1/shared': [DOC('granted-1')],
				'GET /api/v1/workspaces/ws-1/private': [],
				'GET /api/v1/workspaces/ws-1/folders': []
			})
		);
		const vm = createTeamspaces('ws-1');
		await vm.load();

		expect(vm.shared.map((d) => d.id)).toEqual(['granted-1']);
		// A granted document is not implicitly a favourite.
		expect(vm.isFavorite('granted-1')).toBe(false);
	});

	it('exposes folders scoped to a teamspace or private, and loads their docs', async () => {
		const FOLDER = (id: string, teamspace_id: string | null) => ({
			id,
			workspace_id: 'ws-1',
			name: `Folder ${id}`,
			teamspace_id,
			parent_folder_id: null,
			created_by: 'alice',
			created_at: '2026-01-01T00:00:00Z'
		});
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/workspaces/ws-1/teamspaces': [TEAMSPACE],
				'GET /api/v1/favorites': [],
				'GET /api/v1/shared': [],
				'GET /api/v1/workspaces/ws-1/private': [DOC('p1')],
				'GET /api/v1/workspaces/ws-1/folders': [FOLDER('f-ts', 'ts-1'), FOLDER('f-priv', null)],
				'GET /api/v1/folders/f-ts/documents': [DOC('d-in-folder')]
			})
		);
		const vm = createTeamspaces('ws-1');
		await vm.load();

		expect(vm.private.map((d) => d.id)).toEqual(['p1']);
		expect(vm.foldersFor('ts-1').map((n) => n.folder.id)).toEqual(['f-ts']);
		expect(vm.foldersFor(null).map((n) => n.folder.id)).toEqual(['f-priv']);

		await vm.toggleFolder('f-ts');
		expect(vm.foldersFor('ts-1')[0].documents.map((d) => d.id)).toEqual(['d-in-folder']);
	});

	it('reloading preserves expansion and refreshes expanded nodes', async () => {
		const FOLDER = {
			id: 'f-ts',
			workspace_id: 'ws-1',
			name: 'Folder',
			teamspace_id: 'ts-1',
			parent_folder_id: null,
			created_by: 'alice',
			created_at: '2026-01-01T00:00:00Z'
		};
		let folderDocs = [DOC('d-1', 'ts-1')];
		vi.stubGlobal(
			'fetch',
			vi.fn(async (url: string, init?: RequestInit) => {
				const key = `${init?.method ?? 'GET'} ${url}`;
				const routes: Record<string, unknown> = {
					'GET /api/v1/workspaces/ws-1/teamspaces': [TEAMSPACE],
					'GET /api/v1/favorites': [],
					'GET /api/v1/shared': [],
					'GET /api/v1/workspaces/ws-1/private': [],
					'GET /api/v1/workspaces/ws-1/folders': [FOLDER],
					'GET /api/v1/teamspaces/ts-1/documents': [],
					'GET /api/v1/folders/f-ts/documents': folderDocs
				};
				if (!(key in routes)) throw new Error(`unrouted: ${key}`);
				return { ok: true, status: 200, json: async () => routes[key] };
			}) as unknown as typeof fetch
		);
		const vm = createTeamspaces('ws-1');
		await vm.load();
		await vm.toggle('ts-1');
		await vm.toggleFolder('f-ts');
		expect(vm.nodes[0].expanded).toBe(true);
		expect(vm.foldersFor('ts-1')[0].expanded).toBe(true);

		// Simulate a document moving into the folder, then a refresh().
		folderDocs = [DOC('d-1', 'ts-1'), DOC('d-2', 'ts-1')];
		await vm.load();

		// Regression: the tree must NOT collapse, and the folder must show the move.
		expect(vm.nodes[0].expanded).toBe(true);
		expect(vm.foldersFor('ts-1')[0].expanded).toBe(true);
		expect(vm.foldersFor('ts-1')[0].documents.map((d) => d.id)).toEqual(['d-1', 'd-2']);
	});

	it('collapse and re-expand fetch documents only once', async () => {
		const FOLDER = {
			id: 'f-1',
			workspace_id: 'ws-1',
			name: 'Folder',
			teamspace_id: null,
			parent_folder_id: null,
			created_by: 'alice',
			created_at: '2026-01-01T00:00:00Z'
		};
		const fetchMock = routedFetch({
			'GET /api/v1/workspaces/ws-1/teamspaces': [TEAMSPACE],
			'GET /api/v1/favorites': [],
			'GET /api/v1/shared': [],
			'GET /api/v1/workspaces/ws-1/private': [],
			'GET /api/v1/workspaces/ws-1/folders': [FOLDER],
			'GET /api/v1/teamspaces/ts-1/documents': [DOC('d-1', 'ts-1')],
			'GET /api/v1/folders/f-1/documents': [DOC('d-2')]
		});
		vi.stubGlobal('fetch', fetchMock);
		const vm = createTeamspaces('ws-1');
		await vm.load();

		await vm.toggle('ts-1');
		await vm.toggle('ts-1'); // collapse
		expect(vm.nodes[0].expanded).toBe(false);
		await vm.toggle('ts-1'); // re-expand from cache
		expect(vm.nodes[0].expanded).toBe(true);

		await vm.toggleFolder('f-1');
		await vm.toggleFolder('f-1'); // collapse
		expect(vm.foldersFor(null)[0].expanded).toBe(false);
		await vm.toggleFolder('f-1'); // re-expand from cache
		expect(vm.foldersFor(null)[0].expanded).toBe(true);

		const calls = (fetchMock as unknown as ReturnType<typeof vi.fn>).mock.calls;
		expect(calls.filter(([url]) => String(url).includes('/teamspaces/ts-1/documents'))).toHaveLength(1);
		expect(calls.filter(([url]) => String(url).includes('/folders/f-1/documents'))).toHaveLength(1);
	});

	it('toggle, reload and their folder variants ignore unknown ids', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/workspaces/ws-1/teamspaces': [],
				'GET /api/v1/favorites': [],
				'GET /api/v1/shared': [],
				'GET /api/v1/workspaces/ws-1/private': [],
				'GET /api/v1/workspaces/ws-1/folders': []
			})
		);
		const vm = createTeamspaces('ws-1');
		await vm.load();

		// Any fetch for an unknown node would hit an unrouted URL and throw.
		await vm.toggle('nope');
		await vm.toggleFolder('nope');
		await vm.reload('nope');
		await vm.reloadFolder('nope');

		expect(vm.nodes).toHaveLength(0);
		expect(vm.foldersFor(null)).toHaveLength(0);
	});

	it('reload refreshes a teamspace and a folder without toggling', async () => {
		const FOLDER = {
			id: 'f-1',
			workspace_id: 'ws-1',
			name: 'Folder',
			teamspace_id: null,
			parent_folder_id: null,
			created_by: 'alice',
			created_at: '2026-01-01T00:00:00Z'
		};
		const NESTED = { ...FOLDER, id: 'f-child', parent_folder_id: 'f-1' };
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/workspaces/ws-1/teamspaces': [TEAMSPACE],
				'GET /api/v1/favorites': [],
				'GET /api/v1/shared': [],
				'GET /api/v1/workspaces/ws-1/private': [],
				'GET /api/v1/workspaces/ws-1/folders': [FOLDER, NESTED],
				'GET /api/v1/teamspaces/ts-1/documents': [DOC('d-1', 'ts-1')],
				'GET /api/v1/folders/f-1/documents': [DOC('d-2')]
			})
		);
		const vm = createTeamspaces('ws-1');
		await vm.load();
		await vm.load(); // reloading collapsed, unloaded nodes stays lazy
		expect(vm.nodes[0].loaded).toBe(false);

		// Nested folders are not top-level in any scope.
		expect(vm.foldersFor(null).map((n) => n.folder.id)).toEqual(['f-1']);

		await vm.reload('ts-1');
		expect(vm.nodes[0].loaded).toBe(true);
		expect(vm.nodes[0].documents.map((d) => d.id)).toEqual(['d-1']);

		await vm.reloadFolder('f-1');
		expect(vm.foldersFor(null)[0].loaded).toBe(true);
		expect(vm.foldersFor(null)[0].documents.map((d) => d.id)).toEqual(['d-2']);
	});

	it('createFolder appends a collapsed node scoped to its parent', async () => {
		const FOLDER = {
			id: 'f-new',
			workspace_id: 'ws-1',
			name: 'Notes',
			teamspace_id: null,
			parent_folder_id: null,
			created_by: 'alice',
			created_at: '2026-01-01T00:00:00Z'
		};
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/workspaces/ws-1/teamspaces': [],
				'GET /api/v1/favorites': [],
				'GET /api/v1/shared': [],
				'GET /api/v1/workspaces/ws-1/private': [],
				'GET /api/v1/workspaces/ws-1/folders': [],
				'POST /api/v1/workspaces/ws-1/folders': FOLDER
			})
		);
		const vm = createTeamspaces('ws-1');
		await vm.load();

		const created = await vm.createFolder('Notes', null);

		expect(created?.id).toBe('f-new');
		const node = vm.foldersFor(null)[0];
		expect(node.folder.id).toBe('f-new');
		expect(node.expanded).toBe(false); // lazy until toggled
		expect(node.loaded).toBe(false);
		expect(vm.error).toBeNull();
	});

	it('surfaces a createFolder failure without adding a node', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async (url: string, init?: RequestInit) => {
				if ((init?.method ?? 'GET') === 'POST') {
					return { ok: false, status: 403, json: async () => ({ detail: 'nope' }) };
				}
				return { ok: true, status: 200, json: async () => [] };
			}) as unknown as typeof fetch
		);
		const vm = createTeamspaces('ws-1');
		await vm.load();

		expect(await vm.createFolder('Denied', null)).toBeNull();
		expect(vm.foldersFor(null)).toHaveLength(0);
		expect(vm.error).toMatch(/403/);
	});
});
