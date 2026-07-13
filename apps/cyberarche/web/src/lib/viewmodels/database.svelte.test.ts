import { afterEach, describe, expect, it, vi } from 'vitest';
import * as Y from 'yjs';

import {
	applyFilters,
	createDatabase,
	OPTION_COLORS,
	sortRows,
	type CellValue,
	type Property,
	type Row
} from './database.svelte';

vi.stubGlobal('crypto', {
	randomUUID: () => `${Math.random().toString(16).slice(2)}-x-x-x-x`
});

describe('database view-model', () => {
	afterEach(() => vi.useRealTimers());

	it('seeds a schema, adds rows/columns, edits cells, groups and sorts', () => {
		const doc = new Y.Doc();
		const db = createDatabase(doc, 'blk1');

		// Seeded starter schema: Name (text) + Status (select).
		expect(db.properties.map((p) => p.type)).toEqual(['text', 'select']);
		const name = db.properties[0];
		const status = db.properties[1];
		const doing = status.options!.find((o) => o.name === 'Doing')!;

		const r1 = db.addRow({ [name.id]: 'Task A', [status.id]: doing.id });
		const r2 = db.addRow({ [name.id]: 'Task B' });
		expect(db.rows.length).toBe(2);

		// Edit a cell.
		db.setCell(r2.id, name.id, 'Task B renamed');
		expect(db.rows.find((r) => r.id === r2.id)!.values[name.id]).toBe('Task B renamed');

		// Add a column and remove a row.
		const num = db.addProperty('number');
		expect(db.properties.some((p) => p.id === num.id && p.type === 'number')).toBe(true);
		db.removeRow(r1.id);
		expect(db.rows.length).toBe(1);

		// Group by the select property for the board.
		db.addRow({ [name.id]: 'Task C', [status.id]: doing.id });
		const groups = db.groupBy(status.id);
		expect(groups.get(doing.id)?.length).toBe(1); // Task C
		expect(groups.get('')?.length).toBe(1); // Task B (no status)
	});

	it('persists across a fresh view-model over the same doc', () => {
		const doc = new Y.Doc();
		const a = createDatabase(doc, 'blk2');
		const name = a.properties[0];
		a.addRow({ [name.id]: 'Persisted' });

		const b = createDatabase(doc, 'blk2'); // reopen the same block
		expect(b.rows.length).toBe(1);
		expect(b.rows[0].values[name.id]).toBe('Persisted');
	});

	it('filters rows by typed operators (AND across filters)', () => {
		const props: Property[] = [
			{ id: 'name', name: 'Name', type: 'text' },
			{ id: 'n', name: 'N', type: 'number' },
			{ id: 'done', name: 'Done', type: 'checkbox' },
			{
				id: 'status',
				name: 'Status',
				type: 'select',
				options: [{ id: 'op1', name: 'Doing', color: '#000' }]
			}
		];
		const rows = [
			{ id: 'a', order: 0, values: { name: 'Alpha', n: 5, done: true, status: 'op1' } },
			{ id: 'b', order: 1, values: { name: 'Beta', n: 2, done: false, status: null } },
			{ id: 'c', order: 2, values: { name: 'Alpine', n: 9, done: true, status: 'op1' } }
		];

		// text contains
		expect(applyFilters(rows, [{ id: 'f', propertyId: 'name', op: 'contains', value: 'alp' }], props).map((r) => r.id)).toEqual(['a', 'c']);
		// number greater-than
		expect(applyFilters(rows, [{ id: 'f', propertyId: 'n', op: 'gt', value: 4 }], props).map((r) => r.id)).toEqual(['a', 'c']);
		// checkbox unchecked
		expect(applyFilters(rows, [{ id: 'f', propertyId: 'done', op: 'unchecked', value: null }], props).map((r) => r.id)).toEqual(['b']);
		// select is empty
		expect(applyFilters(rows, [{ id: 'f', propertyId: 'status', op: 'empty', value: null }], props).map((r) => r.id)).toEqual(['b']);
		// two filters AND: contains "alp" AND n < 8
		expect(
			applyFilters(
				rows,
				[
					{ id: 'f1', propertyId: 'name', op: 'contains', value: 'alp' },
					{ id: 'f2', propertyId: 'n', op: 'lt', value: 8 }
				],
				props
			).map((r) => r.id)
		).toEqual(['a']);
	});

	it('persists filters in the doc', () => {
		const doc = new Y.Doc();
		const a = createDatabase(doc, 'blkf');
		a.addFilter(a.properties[0].id);
		expect(a.filters.length).toBe(1);
		const b = createDatabase(doc, 'blkf');
		expect(b.filters.length).toBe(1);
	});

	it('sorts rows by a property without mutating stored order', () => {
		const rows = [
			{ id: 'a', order: 0, values: { p: 3 } },
			{ id: 'b', order: 1, values: { p: 1 } },
			{ id: 'c', order: 2, values: { p: 2 } }
		];
		expect(sortRows(rows, 'p', 'asc').map((r) => r.id)).toEqual(['b', 'c', 'a']);
		expect(sortRows(rows, 'p', 'desc').map((r) => r.id)).toEqual(['a', 'c', 'b']);
		expect(rows.map((r) => r.id)).toEqual(['a', 'b', 'c']); // unchanged
	});

	it('sorts strings lexically and pushes missing values to the end', () => {
		const rows = [
			{ id: 'a', order: 0, values: { p: 'pear' as CellValue } },
			{ id: 'b', order: 1, values: { p: null as CellValue } },
			{ id: 'c', order: 2, values: { p: 'apple' as CellValue } },
			{ id: 'd', order: 3, values: {} as Record<string, CellValue> }
		];
		expect(sortRows(rows, 'p', 'asc').map((r) => r.id)).toEqual(['c', 'a', 'b', 'd']);
		// Missing values stay last even when descending.
		expect(sortRows(rows, 'p', 'desc').map((r) => r.id)).toEqual(['a', 'c', 'b', 'd']);
	});

	it('hydrates from a mirrored snapshot instead of reseeding', () => {
		const doc = new Y.Doc();
		const props: Property[] = [{ id: 'p1', name: 'Title', type: 'text' }];
		const db = createDatabase(doc, 'blk3', {
			initial: {
				properties: props,
				rows: [
					{ id: 'r1', values: { p1: 'first' } },
					{ id: 'r2', values: { p1: 'second' } }
				]
			}
		});

		expect(db.properties.map((p) => p.name)).toEqual(['Title']);
		expect(db.rows.map((r) => [r.id, r.order])).toEqual([
			['r1', 0],
			['r2', 1]
		]);
	});

	it('seeds the starter schema when the snapshot is empty', () => {
		const doc = new Y.Doc();
		const db = createDatabase(doc, 'blk4', { initial: { properties: [], rows: [] } });
		expect(db.properties.map((p) => p.name)).toEqual(['Name', 'Status']);
	});

	it('renames, retypes, and removes properties', () => {
		const doc = new Y.Doc();
		const db = createDatabase(doc, 'blk5');
		const name = db.properties[0];
		const status = db.properties[1];

		db.renameProperty(name.id, 'Task');
		expect(db.properties[0].name).toBe('Task');

		// text -> select gains an empty options list…
		db.setPropertyType(name.id, 'select');
		expect(db.properties[0].options).toEqual([]);
		// …select -> select keeps the existing options…
		db.setPropertyType(status.id, 'select');
		expect(db.properties[1].options!.length).toBe(3);
		// …and select -> text drops them.
		db.setPropertyType(status.id, 'text');
		expect(db.properties[1].options).toBeUndefined();

		db.removeProperty(name.id);
		expect(db.properties.map((p) => p.id)).toEqual([status.id]);
	});

	it('addProperty("select") starts with options; addOption cycles the palette', () => {
		const doc = new Y.Doc();
		const db = createDatabase(doc, 'blk6');
		const select = db.addProperty('select');
		expect(select.options).toEqual([]);

		for (let i = 0; i < OPTION_COLORS.length; i += 1) db.addOption(select.id, `o${i}`);
		const wrapped = db.addOption(select.id, 'again');

		const stored = db.properties.find((p) => p.id === select.id)!;
		expect(stored.options!.map((o) => o.color)).toEqual([...OPTION_COLORS, OPTION_COLORS[0]]);
		expect(wrapped.color).toBe(OPTION_COLORS[0]);
	});

	it('addOption on an unknown property leaves the schema unchanged', () => {
		const doc = new Y.Doc();
		const db = createDatabase(doc, 'blk7');
		const before = db.properties;

		const option = db.addOption('ghost', 'Nope');

		expect(option.color).toBe(OPTION_COLORS[0]); // 0 existing options
		expect(db.properties).toEqual(before);
	});

	it('links a row to its page document, ignoring unknown rows', () => {
		const doc = new Y.Doc();
		const db = createDatabase(doc, 'blk8');
		const row = db.addRow();

		db.setRowPage(row.id, 'doc-9');
		expect(db.rows[0].pageId).toBe('doc-9');

		db.setRowPage('ghost', 'doc-9'); // no such row: a no-op
		db.setCell('ghost', 'p', 'x'); // same for cells
		expect(db.rows.length).toBe(1);
	});

	it('keeps row order monotonic after deletions', () => {
		const doc = new Y.Doc();
		const db = createDatabase(doc, 'blk9');
		const r1 = db.addRow();
		const r2 = db.addRow();
		expect([r1.order, r2.order]).toEqual([0, 1]);

		db.removeRow(r1.id);
		const r3 = db.addRow();
		expect(r3.order).toBe(2); // never reuses a freed slot
	});

	it('manages filters: defaulting, updating, removing', () => {
		const doc = new Y.Doc();
		const db = createDatabase(doc, 'blk10');
		const name = db.properties[0];
		const status = db.properties[1];

		db.addFilter(); // no property given: defaults to the first
		expect(db.filters[0].propertyId).toBe(name.id);
		expect(db.filters[0].op).toBe('contains'); // first text operator

		db.addFilter(status.id);
		expect(db.filters[1].op).toBe('is'); // first select operator

		db.updateFilter(db.filters[0].id, { op: 'equals', value: 'Task' });
		expect(db.filters[0].op).toBe('equals');
		expect(db.filters[0].value).toBe('Task');
		expect(db.filters[1].value).toBeNull(); // others untouched

		db.removeFilter(db.filters[0].id);
		expect(db.filters.map((f) => f.propertyId)).toEqual([status.id]);
	});

	it('addFilter is a no-op when the schema has no properties', () => {
		const doc = new Y.Doc();
		const db = createDatabase(doc, 'blk11');
		for (const p of [...db.properties]) db.removeProperty(p.id);

		db.addFilter();
		expect(db.filters).toEqual([]);
	});

	it('debounces the data.db mirror and strips row order', () => {
		vi.useFakeTimers();
		const doc = new Y.Doc();
		const onMirror = vi.fn();
		const db = createDatabase(doc, 'blk12', { onMirror });
		const name = db.properties[0];

		const row = db.addRow({ [name.id]: 'A' });
		db.setCell(row.id, name.id, 'B'); // a rapid follow-up edit
		vi.advanceTimersByTime(399);
		expect(onMirror).not.toHaveBeenCalled();
		vi.advanceTimersByTime(1);

		expect(onMirror).toHaveBeenCalledTimes(1); // coalesced
		const snapshot = onMirror.mock.calls[0][0];
		expect(snapshot.properties.map((p: Property) => p.name)).toEqual(['Name', 'Status']);
		expect(snapshot.rows).toEqual([{ id: row.id, values: { [name.id]: 'B' } }]);

		db.removeRow(row.id); // deletions mirror too
		vi.advanceTimersByTime(400);
		expect(onMirror).toHaveBeenCalledTimes(2);
		expect(onMirror.mock.calls[1][0].rows).toEqual([]);
	});

	it('destroy cancels the pending mirror and stops observing', () => {
		vi.useFakeTimers();
		const doc = new Y.Doc();
		const onMirror = vi.fn();
		const db = createDatabase(doc, 'blk13', { onMirror });
		db.addRow();

		db.destroy();
		vi.advanceTimersByTime(400);
		expect(onMirror).not.toHaveBeenCalled();

		// A later (e.g. remote) change no longer updates the dead view-model.
		doc.getMap<unknown>('db:blk13').set('r-late', { id: 'r-late', order: 9, values: {} });
		expect(db.rows.map((r) => r.id)).not.toContain('r-late');
	});

	it('reflects remote updates to the shared map', () => {
		const doc = new Y.Doc();
		const db = createDatabase(doc, 'blk14');
		doc.transact(() => {
			doc.getMap<unknown>('db:blk14').set('r-remote', { id: 'r-remote', order: 0, values: {} });
		}, 'remote');
		expect(db.rows.map((r) => r.id)).toEqual(['r-remote']);
	});

	it('covers every filter operator', () => {
		const props: Property[] = [{ id: 'p', name: 'P', type: 'text' }];
		const match = (value: CellValue, op: string, fv: CellValue = null) =>
			applyFilters(
				[{ id: 'r', order: 0, values: { p: value } } as Row],
				[{ id: 'f', propertyId: 'p', op, value: fv }],
				props
			).length === 1;

		expect(match('', 'empty')).toBe(true);
		expect(match('x', 'empty')).toBe(false);
		expect(match('x', 'not_empty')).toBe(true);
		expect(match(null, 'not_empty')).toBe(false);
		expect(match(true, 'checked')).toBe(true);
		expect(match(false, 'checked')).toBe(false);
		expect(match(false, 'unchecked')).toBe(true);
		expect(match('Alpha', 'contains', 'ALP')).toBe(true); // case-insensitive
		expect(match(null, 'contains', 'x')).toBe(false);
		expect(match('a', 'equals', 'a')).toBe(true);
		expect(match('a', 'is', 'b')).toBe(false);
		expect(match('a', 'is_not', 'b')).toBe(true);
		expect(match(2, 'eq', 2)).toBe(true);
		expect(match(2, 'ne', 2)).toBe(false);
		expect(match(2, 'gt', 1)).toBe(true);
		expect(match(2, 'lt', 1)).toBe(false);
		expect(match(2, 'gte', 2)).toBe(true);
		expect(match(2, 'lte', 1)).toBe(false);
		expect(match('2026-01-01', 'before', '2026-02-01')).toBe(true);
		expect(match('', 'before', '2026-02-01')).toBe(false); // empty dates never match
		expect(match('2026-03-01', 'after', '2026-02-01')).toBe(true);
		expect(match(null, 'after', '2026-02-01')).toBe(false);
		expect(match('anything', 'unknown_op')).toBe(true); // permissive default
	});

	it('applyFilters ignores filters on unknown properties and empty filter lists', () => {
		const props: Property[] = [{ id: 'p', name: 'P', type: 'text' }];
		const rows = [{ id: 'r', order: 0, values: { p: 'x' } }];

		expect(applyFilters(rows, [], props)).toBe(rows); // untouched fast path
		expect(
			applyFilters(rows, [{ id: 'f', propertyId: 'ghost', op: 'empty', value: null }], props)
		).toEqual(rows);
	});
});
