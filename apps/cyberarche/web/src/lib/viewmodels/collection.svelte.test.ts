import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { CollectionRow, PropertyDef, PropertyType } from '$lib/api/collections';
import {
	createCollection,
	createCollectionList,
	groupRows,
	operatorsForType
} from './collection.svelte';

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

/** queryView now returns `{ rows, related }`; a route may still be written as a
 * bare rows array for brevity and is wrapped here to the new shape. */
function wrapRows(url: string, body: unknown): unknown {
	if (/\/views\/[^/]+\/rows$/.test(url) && Array.isArray(body)) {
		return { rows: body, related: [] };
	}
	return body;
}

function routedFetch(routes: Record<string, unknown>) {
	return vi.fn(async (url: string, init?: RequestInit) => {
		const key = `${init?.method ?? 'GET'} ${url}`;
		const body = routes[key];
		if (body === undefined) throw new Error(`unrouted: ${key}`);
		return { ok: true, status: 200, json: async () => wrapRows(url, body) };
	}) as unknown as typeof fetch;
}

interface RecordedCall {
	method: string;
	url: string;
	body: Record<string, unknown> | undefined;
}

/** Like routedFetch, but records each request (parsed body included) and lets a
 * route be a function of the request body so PATCH responses can echo it back. */
function recordingFetch(routes: Record<string, unknown>) {
	const calls: RecordedCall[] = [];
	const fn = vi.fn(async (url: string, init?: RequestInit) => {
		const method = init?.method ?? 'GET';
		const body =
			typeof init?.body === 'string' ? JSON.parse(init.body) : undefined;
		calls.push({ method, url, body });
		const route = routes[`${method} ${url}`];
		if (route === undefined) throw new Error(`unrouted: ${method} ${url}`);
		const resolved = typeof route === 'function' ? route(body) : route;
		return { ok: true, status: 200, json: async () => wrapRows(url, resolved) };
	});
	return { fetch: fn as unknown as typeof fetch, calls };
}

const VIEW = (patch: Record<string, unknown> = {}) => ({
	id: 'v1',
	name: 'Table',
	kind: 'table',
	filters: [],
	sorts: [],
	group_by: null,
	date_by: null,
	...patch
});

/** A recording fetch wired for filter/sort mutation tests: load + re-query + a
 * PATCH view that echoes back whatever filters/sorts the VM sent. */
function viewEditFetch() {
	return recordingFetch({
		'GET /api/v1/collections/c1': COLLECTION(),
		'GET /api/v1/collections/c1/views/v1/rows': [ROW('r1')],
		'PATCH /api/v1/collections/c1/views/v1': (body: Record<string, unknown>) =>
			VIEW({ filters: body.filters ?? [], sorts: body.sorts ?? [] })
	});
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
			if (key === 'GET /api/v1/collections/c1/views/v1/rows')
				return ok({ rows: [ROW('r1')], related: [] });
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

describe('operatorsForType', () => {
	const ops = (type: PropertyType) => operatorsForType(type).map((o) => o.value);

	it('offers checkbox only equality operators', () => {
		expect(ops('checkbox')).toEqual(['eq', 'neq']);
	});

	it('offers text/url contains + emptiness but not numeric comparisons', () => {
		expect(ops('text')).toEqual(['eq', 'neq', 'contains', 'is_empty', 'not_empty']);
		expect(ops('url')).toEqual(ops('text'));
		expect(ops('text')).not.toContain('gt');
	});

	it('offers number comparisons but not contains', () => {
		expect(ops('number')).toEqual(['eq', 'neq', 'gt', 'lt', 'is_empty', 'not_empty']);
		expect(ops('number')).not.toContain('contains');
	});

	it('offers multi_select membership + emptiness only', () => {
		expect(ops('multi_select')).toEqual(['contains', 'is_empty', 'not_empty']);
	});

	it('offers date equality + comparisons + emptiness', () => {
		expect(ops('date')).toEqual(['eq', 'gt', 'lt', 'is_empty', 'not_empty']);
	});

	it('labels every operator', () => {
		for (const op of operatorsForType('number')) expect(op.label.length).toBeGreaterThan(0);
	});
});

describe('collection ViewModel — filters', () => {
	beforeEach(() => vi.restoreAllMocks());

	it('addFilter persists the new filters via updateView then re-queries', async () => {
		const { fetch, calls } = viewEditFetch();
		vi.stubGlobal('fetch', fetch);
		const vm = createCollection('c1');
		await vm.load();
		calls.length = 0;

		await vm.addFilter('p1', 'eq', 'todo');

		const patch = calls.find((c) => c.method === 'PATCH');
		expect(patch?.url).toBe('/api/v1/collections/c1/views/v1');
		expect(patch?.body?.filters).toEqual([{ property_id: 'p1', op: 'eq', value: 'todo' }]);
		// Re-queried rows after the patch.
		expect(calls.some((c) => c.url.endsWith('/views/v1/rows'))).toBe(true);
		expect(vm.filters).toEqual([{ property_id: 'p1', op: 'eq', value: 'todo' }]);
		expect(vm.activeFilterCount).toBe(1);
	});

	it('updateFilter patches the rule at the index', async () => {
		const { fetch, calls } = viewEditFetch();
		vi.stubGlobal('fetch', fetch);
		const vm = createCollection('c1');
		await vm.load();
		await vm.addFilter('p1', 'eq', 'todo');
		calls.length = 0;

		await vm.updateFilter(0, { op: 'neq', value: 'done' });

		expect(vm.filters).toEqual([{ property_id: 'p1', op: 'neq', value: 'done' }]);
	});

	it('removeFilter drops the rule and lowers the active count', async () => {
		const { fetch } = viewEditFetch();
		vi.stubGlobal('fetch', fetch);
		const vm = createCollection('c1');
		await vm.load();
		await vm.addFilter('p1', 'eq', 'todo');
		expect(vm.activeFilterCount).toBe(1);

		await vm.removeFilter(0);
		expect(vm.filters).toEqual([]);
		expect(vm.activeFilterCount).toBe(0);
	});
});

describe('collection ViewModel — sorts', () => {
	beforeEach(() => vi.restoreAllMocks());

	it('addSort persists the sort via updateView then re-queries', async () => {
		const { fetch, calls } = viewEditFetch();
		vi.stubGlobal('fetch', fetch);
		const vm = createCollection('c1');
		await vm.load();
		calls.length = 0;

		await vm.addSort('p1', 'desc');

		const patch = calls.find((c) => c.method === 'PATCH');
		expect(patch?.body?.sorts).toEqual([{ property_id: 'p1', direction: 'desc' }]);
		expect(calls.some((c) => c.url.endsWith('/views/v1/rows'))).toBe(true);
		expect(vm.sorts).toEqual([{ property_id: 'p1', direction: 'desc' }]);
		expect(vm.activeSortCount).toBe(1);
	});

	it('moveSort reorders adjacent sorts', async () => {
		const { fetch } = viewEditFetch();
		vi.stubGlobal('fetch', fetch);
		const vm = createCollection('c1');
		await vm.load();
		await vm.addSort('p1', 'asc');
		await vm.addSort('__title__', 'desc');
		expect(vm.sorts.map((s) => s.property_id)).toEqual(['p1', '__title__']);

		await vm.moveSort(1, 'up');
		expect(vm.sorts.map((s) => s.property_id)).toEqual(['__title__', 'p1']);
	});

	it('moveSort is a no-op past the ends', async () => {
		const { fetch } = viewEditFetch();
		vi.stubGlobal('fetch', fetch);
		const vm = createCollection('c1');
		await vm.load();
		await vm.addSort('p1', 'asc');

		await vm.moveSort(0, 'up'); // already first
		expect(vm.sorts.map((s) => s.property_id)).toEqual(['p1']);
	});

	it('removeSort drops the sort', async () => {
		const { fetch } = viewEditFetch();
		vi.stubGlobal('fetch', fetch);
		const vm = createCollection('c1');
		await vm.load();
		await vm.addSort('p1', 'asc');

		await vm.removeSort(0);
		expect(vm.sorts).toEqual([]);
		expect(vm.activeSortCount).toBe(0);
	});
});

describe('collection ViewModel — board views', () => {
	beforeEach(() => vi.restoreAllMocks());

	function boardFetch() {
		return recordingFetch({
			'GET /api/v1/collections/c1': COLLECTION(),
			'GET /api/v1/collections/c1/views/v1/rows': [
				ROW('r1', { properties: { p1: 'todo' } }),
				ROW('r2', { properties: { p1: 'done' } })
			],
			'GET /api/v1/collections/c1/views/v2/rows': [ROW('r1', { properties: { p1: 'todo' } })],
			'POST /api/v1/collections/c1/views': VIEW({ id: 'v2', name: 'Board', kind: 'board' }),
			'PATCH /api/v1/collections/c1/views/v1': (body: Record<string, unknown>) =>
				VIEW({ group_by: body.group_by ?? null }),
			'PATCH /api/v1/collections/c1/rows/r1': (body: Record<string, unknown>) =>
				ROW('r1', {
					properties: { p1: (body.values as Record<string, unknown>)?.p1 ?? null }
				})
		});
	}

	it('createViewOfKind creates, appends, selects, and re-queries', async () => {
		const { fetch, calls } = boardFetch();
		vi.stubGlobal('fetch', fetch);
		const vm = createCollection('c1');
		await vm.load();
		calls.length = 0;

		const view = await vm.createViewOfKind('Board', 'board');

		expect(view?.id).toBe('v2');
		expect(calls.find((c) => c.method === 'POST')?.body).toEqual({
			name: 'Board',
			kind: 'board'
		});
		expect(vm.collection?.views.map((v) => v.id)).toEqual(['v1', 'v2']);
		expect(vm.currentView?.id).toBe('v2');
		// Re-queried the new view's rows.
		expect(calls.some((c) => c.url.endsWith('/views/v2/rows'))).toBe(true);
		expect(vm.rows.map((r) => r.id)).toEqual(['r1']);
	});

	it('setBoardGroupBy persists group_by and updates the in-memory view', async () => {
		const { fetch, calls } = boardFetch();
		vi.stubGlobal('fetch', fetch);
		const vm = createCollection('c1');
		await vm.load();
		calls.length = 0;

		await vm.setBoardGroupBy('p1');

		const patch = calls.find((c) => c.method === 'PATCH');
		expect(patch?.url).toBe('/api/v1/collections/c1/views/v1');
		expect(patch?.body?.group_by).toBe('p1');
		expect(vm.currentView?.group_by).toBe('p1');
		expect(vm.groupByProperty?.id).toBe('p1');
	});

	it('exposes the select properties available to group by', async () => {
		const { fetch } = boardFetch();
		vi.stubGlobal('fetch', fetch);
		const vm = createCollection('c1');
		await vm.load();
		expect(vm.selectProperties.map((p) => p.id)).toEqual(['p1']);
	});

	it('setRowGroup sets the property and moves the row to the new group', async () => {
		const { fetch } = boardFetch();
		vi.stubGlobal('fetch', fetch);
		const vm = createCollection('c1');
		await vm.load();
		await vm.setBoardGroupBy('p1');

		const before = groupRows(vm.rows, vm.groupByProperty);
		expect(before.find((g) => g.key === 'todo')?.rows.map((r) => r.id)).toEqual(['r1']);

		await vm.setRowGroup('r1', 'p1', 'done');

		expect(vm.rows.find((r) => r.id === 'r1')?.properties.p1).toBe('done');
		const after = groupRows(vm.rows, vm.groupByProperty);
		expect(after.find((g) => g.key === 'todo')?.rows).toEqual([]);
		// r1 moved into the "done" group; row-array order (r1 before r2) is kept.
		expect(after.find((g) => g.key === 'done')?.rows.map((r) => r.id)).toEqual(['r1', 'r2']);
	});

	it('setRowGroup with null moves the row to Uncategorized', async () => {
		const { fetch } = boardFetch();
		vi.stubGlobal('fetch', fetch);
		const vm = createCollection('c1');
		await vm.load();
		await vm.setBoardGroupBy('p1');

		await vm.setRowGroup('r1', 'p1', null);

		const groups = groupRows(vm.rows, vm.groupByProperty);
		expect(groups.at(-1)?.key).toBeNull();
		expect(groups.at(-1)?.rows.map((r) => r.id)).toEqual(['r1']);
	});
});

describe('collection ViewModel — calendar views', () => {
	beforeEach(() => vi.restoreAllMocks());

	const CAL_COLLECTION = () =>
		COLLECTION({
			properties: [
				{ id: 'p1', name: 'Status', type: 'select', options: ['todo', 'done'] },
				{ id: 'due', name: 'Due', type: 'date', options: [] }
			]
		});

	function calFetch() {
		return recordingFetch({
			'GET /api/v1/collections/c1': CAL_COLLECTION(),
			'GET /api/v1/collections/c1/views/v1/rows': [ROW('r1')],
			'PATCH /api/v1/collections/c1/views/v1': (body: Record<string, unknown>) =>
				VIEW({ date_by: body.date_by ?? null })
		});
	}

	it('dateProperties lists only date-typed properties', async () => {
		const { fetch } = calFetch();
		vi.stubGlobal('fetch', fetch);
		const vm = createCollection('c1');
		await vm.load();
		expect(vm.dateProperties.map((p) => p.id)).toEqual(['due']);
	});

	it('setDateBy persists date_by and updates the in-memory view', async () => {
		const { fetch, calls } = calFetch();
		vi.stubGlobal('fetch', fetch);
		const vm = createCollection('c1');
		await vm.load();
		calls.length = 0;

		await vm.setDateBy('due');

		const patch = calls.find((c) => c.method === 'PATCH');
		expect(patch?.url).toBe('/api/v1/collections/c1/views/v1');
		expect(patch?.body?.date_by).toBe('due');
		expect(vm.currentView?.date_by).toBe('due');
		expect(vm.dateByProperty?.id).toBe('due');
	});

	it('setDateBy(null) clears the anchored date property', async () => {
		const { fetch } = calFetch();
		vi.stubGlobal('fetch', fetch);
		const vm = createCollection('c1');
		await vm.load();
		await vm.setDateBy('due');

		await vm.setDateBy(null);

		expect(vm.currentView?.date_by).toBeNull();
		expect(vm.dateByProperty).toBeUndefined();
	});
});

describe('collection ViewModel — relations & rollups', () => {
	beforeEach(() => vi.restoreAllMocks());

	const REL_COLLECTION = () =>
		COLLECTION({
			properties: [{ id: 'rel', name: 'Tasks', type: 'relation', options: [], relation_collection_id: 'c2' }]
		});

	it('relatedTitle resolves linked ids from the query result, falling back to Untitled', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/collections/c1': REL_COLLECTION(),
				'GET /api/v1/collections/c1/views/v1/rows': {
					rows: [ROW('r1', { properties: { rel: ['t1'] } })],
					related: [{ id: 't1', title: 'Design' }]
				}
			})
		);
		const vm = createCollection('c1');
		await vm.load();
		expect(vm.relatedTitle('t1')).toBe('Design');
		expect(vm.relatedTitle('unknown')).toBe('Untitled');
	});

	it('setRelation writes the id list and reflects the server row', async () => {
		const { fetch, calls } = recordingFetch({
			'GET /api/v1/collections/c1': REL_COLLECTION(),
			'GET /api/v1/collections/c1/views/v1/rows': {
				rows: [ROW('r1', { properties: { rel: [] } })],
				related: []
			},
			'PATCH /api/v1/collections/c1/rows/r1': (body: Record<string, unknown>) =>
				ROW('r1', { properties: { rel: (body.values as Record<string, unknown>)?.rel ?? [] } })
		});
		vi.stubGlobal('fetch', fetch);
		const vm = createCollection('c1');
		await vm.load();

		await vm.setRelation('r1', 'rel', ['t1', 't2']);

		const patch = calls.find((c) => c.method === 'PATCH');
		expect(patch?.body).toEqual({ values: { rel: ['t1', 't2'] } });
		expect(vm.rows[0].properties.rel).toEqual(['t1', 't2']);
	});

	it('loadRelationRows fetches the target collection rows for the picker', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/collections/c1': REL_COLLECTION(),
				'GET /api/v1/collections/c1/views/v1/rows': { rows: [], related: [] },
				'GET /api/v1/collections/c2/rows': [{ id: 't1', title: 'Design' }]
			})
		);
		const vm = createCollection('c1');
		await vm.load();
		const options = await vm.loadRelationRows('c2');
		expect(options).toEqual([{ id: 't1', title: 'Design' }]);
		expect(vm.relationProperties.map((p) => p.id)).toEqual(['rel']);
	});
});

describe('groupRows', () => {
	const property: PropertyDef = {
		id: 'status',
		name: 'Status',
		type: 'select',
		options: ['todo', 'doing', 'done']
	};
	const row = (id: string, status?: string): CollectionRow =>
		({ id, properties: status === undefined ? {} : { status } }) as unknown as CollectionRow;

	it('creates a group per option in option order plus a trailing Uncategorized', () => {
		const groups = groupRows(
			[row('a', 'done'), row('b', 'todo'), row('c')],
			property
		);
		expect(groups.map((g) => g.key)).toEqual(['todo', 'doing', 'done', null]);
		expect(groups.map((g) => g.label)).toEqual(['todo', 'doing', 'done', 'Uncategorized']);
	});

	it('routes empty and unknown values to Uncategorized', () => {
		const groups = groupRows([row('a'), row('b', 'archived'), row('c', 'todo')], property);
		expect(groups.find((g) => g.key === 'todo')?.rows.map((r) => r.id)).toEqual(['c']);
		expect(groups.at(-1)?.key).toBeNull();
		expect(groups.at(-1)?.rows.map((r) => r.id)).toEqual(['a', 'b']);
	});

	it('preserves incoming order within a group', () => {
		const groups = groupRows([row('a', 'todo'), row('b', 'done'), row('c', 'todo')], property);
		expect(groups.find((g) => g.key === 'todo')?.rows.map((r) => r.id)).toEqual(['a', 'c']);
	});

	it('returns a single All group when no property is given', () => {
		const groups = groupRows([row('a', 'todo'), row('b')], undefined);
		expect(groups).toHaveLength(1);
		expect(groups[0].key).toBeNull();
		expect(groups[0].label).toBe('All');
		expect(groups[0].rows.map((r) => r.id)).toEqual(['a', 'b']);
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
