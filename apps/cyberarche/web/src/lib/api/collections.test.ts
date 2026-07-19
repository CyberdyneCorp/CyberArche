import { beforeEach, describe, expect, it, vi, type Mock } from 'vitest';

import {
	addProperty,
	addRow,
	bulkDeleteRows,
	bulkSetRows,
	createCollection,
	createView,
	deleteCollection,
	deleteRow,
	deleteView,
	getCollection,
	listCollectionRows,
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
			options: ['todo', 'done'],
			formula: '',
			relation_collection_id: '',
			rollup_relation_property_id: '',
			rollup_target_property_id: '',
			rollup_function: '',
			reminder_minutes: -1
		});
	});

	it('adds a date property with a reminder lead time', async () => {
		const fetchMock = routedFetch({
			'POST /api/v1/collections/c1/properties': { id: 'c1', properties: [{ id: 'd1' }] }
		});
		vi.stubGlobal('fetch', fetchMock);
		await addProperty('c1', 'Due', 'date', [], '', {}, 1440);
		const init = (fetchMock as unknown as Mock).mock.calls[0][1];
		expect(JSON.parse(init.body)).toEqual({
			name: 'Due',
			type: 'date',
			options: [],
			formula: '',
			relation_collection_id: '',
			rollup_relation_property_id: '',
			rollup_target_property_id: '',
			rollup_function: '',
			reminder_minutes: 1440
		});
	});

	it('adds a formula property, passing the expression through', async () => {
		const fetchMock = routedFetch({
			'POST /api/v1/collections/c1/properties': { id: 'c1', properties: [{ id: 'f1' }] }
		});
		vi.stubGlobal('fetch', fetchMock);
		await addProperty('c1', 'Total', 'formula', [], 'prop("Price") * prop("Qty")');
		const init = (fetchMock as unknown as Mock).mock.calls[0][1];
		expect(JSON.parse(init.body)).toEqual({
			name: 'Total',
			type: 'formula',
			options: [],
			formula: 'prop("Price") * prop("Qty")',
			relation_collection_id: '',
			rollup_relation_property_id: '',
			rollup_target_property_id: '',
			rollup_function: '',
			reminder_minutes: -1
		});
	});

	it('adds a relation property, passing the target collection through', async () => {
		const fetchMock = routedFetch({
			'POST /api/v1/collections/c1/properties': { id: 'c1', properties: [{ id: 'rel' }] }
		});
		vi.stubGlobal('fetch', fetchMock);
		await addProperty('c1', 'Tasks', 'relation', [], '', { relation_collection_id: 'c2' });
		const init = (fetchMock as unknown as Mock).mock.calls[0][1];
		expect(JSON.parse(init.body)).toEqual({
			name: 'Tasks',
			type: 'relation',
			options: [],
			formula: '',
			relation_collection_id: 'c2',
			rollup_relation_property_id: '',
			rollup_target_property_id: '',
			rollup_function: '',
			reminder_minutes: -1
		});
	});

	it('adds a rollup property, passing the relation/target/function through', async () => {
		const fetchMock = routedFetch({
			'POST /api/v1/collections/c1/properties': { id: 'c1', properties: [{ id: 'roll' }] }
		});
		vi.stubGlobal('fetch', fetchMock);
		await addProperty('c1', 'Task count', 'rollup', [], '', {
			rollup_relation_property_id: 'rel',
			rollup_target_property_id: '__title__',
			rollup_function: 'count'
		});
		const init = (fetchMock as unknown as Mock).mock.calls[0][1];
		expect(JSON.parse(init.body)).toEqual({
			name: 'Task count',
			type: 'rollup',
			options: [],
			formula: '',
			relation_collection_id: '',
			rollup_relation_property_id: 'rel',
			rollup_target_property_id: '__title__',
			rollup_function: 'count',
			reminder_minutes: -1
		});
	});

	it('lists a collection rows (id + title) for the relation picker', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/collections/c2/rows': [{ id: 't1', title: 'Design' }]
			})
		);
		const rows = await listCollectionRows('c2');
		expect(rows).toEqual([{ id: 't1', title: 'Design' }]);
	});

	it('adds a row', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({ 'POST /api/v1/collections/c1/rows': { id: 'r1', title: 'X' } })
		);
		const row = await addRow('c1', 'X');
		expect(row.id).toBe('r1');
	});

	it('queries a view for rows, returning the rows + related map', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/collections/c1/views/v1/rows': {
					rows: [{ id: 'r1', title: 'X' }],
					related: [{ id: 't1', title: 'Design' }]
				}
			})
		);
		const result = await queryView('c1', 'v1');
		expect(result.rows.map((r) => r.id)).toEqual(['r1']);
		expect(result.related).toEqual([{ id: 't1', title: 'Design' }]);
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

	it('bulk-deletes rows (POST) and returns the deleted count', async () => {
		const fetchMock = routedFetch({
			'POST /api/v1/collections/c1/rows/bulk-delete': { deleted: 2 }
		});
		vi.stubGlobal('fetch', fetchMock);
		const result = await bulkDeleteRows('c1', ['r1', 'r2']);
		expect(result).toEqual({ deleted: 2 });
		const init = (fetchMock as unknown as Mock).mock.calls[0][1];
		expect(init.method).toBe('POST');
		expect(JSON.parse(init.body)).toEqual({ ids: ['r1', 'r2'] });
	});

	it('bulk-sets one property across rows (POST) and returns the updated count', async () => {
		const fetchMock = routedFetch({
			'POST /api/v1/collections/c1/rows/bulk-set': { updated: 3 }
		});
		vi.stubGlobal('fetch', fetchMock);
		const result = await bulkSetRows('c1', ['r1', 'r2', 'r3'], 'p1', 'done');
		expect(result).toEqual({ updated: 3 });
		const init = (fetchMock as unknown as Mock).mock.calls[0][1];
		expect(init.method).toBe('POST');
		expect(JSON.parse(init.body)).toEqual({
			ids: ['r1', 'r2', 'r3'],
			property_id: 'p1',
			value: 'done'
		});
	});
});
