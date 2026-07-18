import { beforeEach, describe, expect, it, vi, type Mock } from 'vitest';

import {
	addProperty,
	addRow,
	createCollection,
	createView,
	deleteCollection,
	deleteRow,
	deleteView,
	getCollection,
	listCollections,
	queryView,
	removeProperty,
	renameCollection,
	setRowValues,
	updateProperty,
	updateView
} from './collections';

/** Route by "METHOD path" so each client's real request shape is exercised. */
function routedFetch(routes: Record<string, unknown>) {
	return vi.fn(async (url: string, init?: RequestInit) => {
		const key = `${init?.method ?? 'GET'} ${url}`;
		const body = routes[key];
		if (body === undefined) throw new Error(`unrouted: ${key}`);
		return { ok: true, status: 200, json: async () => body, body: init?.body };
	}) as unknown as typeof fetch;
}

describe('collections api client', () => {
	beforeEach(() => vi.restoreAllMocks());

	it('lists collections for a workspace', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({ 'GET /api/v1/workspaces/ws-1/collections': [{ id: 'c1' }] })
		);
		const result = await listCollections('ws-1');
		expect(result).toEqual([{ id: 'c1' }]);
	});

	it('creates a collection with a JSON name body', async () => {
		const fetchMock = routedFetch({
			'POST /api/v1/workspaces/ws-1/collections': { id: 'c1', name: 'Tasks' }
		});
		vi.stubGlobal('fetch', fetchMock);
		const created = await createCollection('ws-1', 'Tasks');
		expect(created.name).toBe('Tasks');
		const init = (fetchMock as unknown as Mock).mock.calls[0][1];
		expect(JSON.parse(init.body)).toEqual({ name: 'Tasks' });
	});

	it('adds a select property with options', async () => {
		const fetchMock = routedFetch({
			'POST /api/v1/collections/c1/properties': { id: 'c1', properties: [{ id: 'p1' }] }
		});
		vi.stubGlobal('fetch', fetchMock);
		await addProperty('c1', 'Status', 'select', ['todo', 'done']);
		const init = (fetchMock as unknown as Mock).mock.calls[0][1];
		expect(JSON.parse(init.body)).toEqual({
			name: 'Status',
			type: 'select',
			options: ['todo', 'done']
		});
	});

	it('adds a row', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({ 'POST /api/v1/collections/c1/rows': { id: 'r1', title: 'X' } })
		);
		const row = await addRow('c1', 'X');
		expect(row.id).toBe('r1');
	});

	it('queries a view for rows', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/collections/c1/views/v1/rows': [{ id: 'r1', title: 'X' }]
			})
		);
		const rows = await queryView('c1', 'v1');
		expect(rows.map((r) => r.id)).toEqual(['r1']);
	});

	it('sets row values via a values map (PATCH)', async () => {
		const fetchMock = routedFetch({
			'PATCH /api/v1/collections/c1/rows/r1': { id: 'r1', properties: { p1: 'todo' } }
		});
		vi.stubGlobal('fetch', fetchMock);
		const updated = await setRowValues('c1', 'r1', { p1: 'todo' });
		expect(updated.properties.p1).toBe('todo');
		const init = (fetchMock as unknown as Mock).mock.calls[0][1];
		expect(JSON.parse(init.body)).toEqual({ values: { p1: 'todo' } });
	});

	it('covers get/rename/delete collection and view + property edits', async () => {
		const fetchMock = routedFetch({
			'GET /api/v1/collections/c1': { id: 'c1' },
			'PATCH /api/v1/collections/c1': { id: 'c1', name: 'Renamed' },
			'DELETE /api/v1/collections/c1': {},
			'PATCH /api/v1/collections/c1/properties/p1': { id: 'c1' },
			'DELETE /api/v1/collections/c1/properties/p1': { id: 'c1' },
			'POST /api/v1/collections/c1/views': { id: 'v2', kind: 'board' },
			'PATCH /api/v1/collections/c1/views/v2': { id: 'v2', name: 'B2' },
			'DELETE /api/v1/collections/c1/views/v2': {},
			'DELETE /api/v1/collections/c1/rows/r1': {}
		});
		vi.stubGlobal('fetch', fetchMock);

		expect((await getCollection('c1')).id).toBe('c1');
		expect((await renameCollection('c1', 'Renamed')).name).toBe('Renamed');
		await deleteCollection('c1');
		await updateProperty('c1', 'p1', { name: 'X', options: ['a'] });
		await removeProperty('c1', 'p1');
		expect((await createView('c1', 'Board', 'board')).id).toBe('v2');
		expect((await updateView('c1', 'v2', { name: 'B2' })).name).toBe('B2');
		await deleteView('c1', 'v2');
		await deleteRow('c1', 'r1');

		expect((fetchMock as unknown as Mock).mock.calls.length).toBe(9);
	});
});
