import { beforeEach, describe, expect, it, vi } from 'vitest';

import { createCollection, createCollectionList } from './collection.svelte';

const COLLECTION = (overrides: Record<string, unknown> = {}) => ({
	id: 'c1',
	workspace_id: 'ws-1',
	name: 'Tasks',
	properties: [{ id: 'p1', name: 'Status', type: 'select', options: ['todo', 'done'] }],
	views: [{ id: 'v1', name: 'Table', kind: 'table', filters: [], sorts: [], group_by: null, date_by: null }],
	created_at: '2026-01-01T00:00:00Z',
	...overrides
});

const ROW = (id: string, extra: Record<string, unknown> = {}) => ({
	id,
	workspace_id: 'ws-1',
	title: `Row ${id}`,
	collection_id: 'c1',
	properties: {},
	created_at: '2026-01-01T00:00:00Z',
	updated_at: '2026-01-01T00:00:00Z',
	...extra
});

function routedFetch(routes: Record<string, unknown>) {
	return vi.fn(async (url: string, init?: RequestInit) => {
		const key = `${init?.method ?? 'GET'} ${url}`;
		const body = routes[key];
		if (body === undefined) throw new Error(`unrouted: ${key}`);
		return { ok: true, status: 200, json: async () => body };
	}) as unknown as typeof fetch;
}

describe('collection ViewModel', () => {
	beforeEach(() => vi.restoreAllMocks());

	it('loads the collection and the first view rows', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/collections/c1': COLLECTION(),
				'GET /api/v1/collections/c1/views/v1/rows': [ROW('r1'), ROW('r2')]
			})
		);
		const vm = createCollection('c1');
		await vm.load();

		expect(vm.collection?.name).toBe('Tasks');
		expect(vm.properties.map((p) => p.id)).toEqual(['p1']);
		expect(vm.rows.map((r) => r.id)).toEqual(['r1', 'r2']);
		expect(vm.currentView?.id).toBe('v1');
	});

	it('adds a row and appends it to state', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/collections/c1': COLLECTION(),
				'GET /api/v1/collections/c1/views/v1/rows': [],
				'POST /api/v1/collections/c1/rows': ROW('r9', { title: 'New' })
			})
		);
		const vm = createCollection('c1');
		await vm.load();
		const row = await vm.addRow('New');

		expect(row?.id).toBe('r9');
		expect(vm.rows.map((r) => r.id)).toEqual(['r9']);
	});

	it('setCell updates the row in place with the server response', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/collections/c1': COLLECTION(),
				'GET /api/v1/collections/c1/views/v1/rows': [ROW('r1')],
				'PATCH /api/v1/collections/c1/rows/r1': ROW('r1', { properties: { p1: 'todo' } })
			})
		);
		const vm = createCollection('c1');
		await vm.load();
		await vm.setCell('r1', 'p1', 'todo');

		expect(vm.rows[0].properties.p1).toBe('todo');
	});

	it('setCell reloads rows when the update fails', async () => {
		const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
			const key = `${init?.method ?? 'GET'} ${url}`;
			if (key === 'GET /api/v1/collections/c1') return ok(COLLECTION());
			if (key === 'GET /api/v1/collections/c1/views/v1/rows') return ok([ROW('r1')]);
			if (key === 'PATCH /api/v1/collections/c1/rows/r1')
				return { ok: false, status: 422, json: async () => ({ detail: 'bad option' }) };
			throw new Error(`unrouted: ${key}`);
		});
		function ok(body: unknown) {
			return { ok: true, status: 200, json: async () => body };
		}
		vi.stubGlobal('fetch', fetchMock as unknown as typeof fetch);

		const vm = createCollection('c1');
		await vm.load();
		await vm.setCell('r1', 'p1', 'nope');

		expect(vm.error).toContain('bad option');
		// Fell back to server truth (a fresh queryView call).
		expect(vm.rows.map((r) => r.id)).toEqual(['r1']);
	});

	it('addProperty replaces the collection with the new schema', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/collections/c1': COLLECTION({ properties: [] }),
				'GET /api/v1/collections/c1/views/v1/rows': [],
				'POST /api/v1/collections/c1/properties': COLLECTION()
			})
		);
		const vm = createCollection('c1');
		await vm.load();
		expect(vm.properties).toEqual([]);
		await vm.addProperty('Status', 'select', ['todo', 'done']);
		expect(vm.properties.map((p) => p.id)).toEqual(['p1']);
	});

	it('deleteRow removes optimistically', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/collections/c1': COLLECTION(),
				'GET /api/v1/collections/c1/views/v1/rows': [ROW('r1'), ROW('r2')],
				'DELETE /api/v1/collections/c1/rows/r1': {}
			})
		);
		const vm = createCollection('c1');
		await vm.load();
		await vm.deleteRow('r1');
		expect(vm.rows.map((r) => r.id)).toEqual(['r2']);
	});
});

describe('collection list ViewModel', () => {
	beforeEach(() => vi.restoreAllMocks());

	it('loads and creates collections', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/workspaces/ws-1/collections': [COLLECTION()],
				'POST /api/v1/workspaces/ws-1/collections': COLLECTION({ id: 'c2', name: 'Notes' })
			})
		);
		const vm = createCollectionList('ws-1');
		await vm.load();
		expect(vm.collections.map((c) => c.id)).toEqual(['c1']);

		const created = await vm.create('Notes');
		expect(created?.id).toBe('c2');
		expect(vm.collections.map((c) => c.id)).toEqual(['c1', 'c2']);
	});
});
