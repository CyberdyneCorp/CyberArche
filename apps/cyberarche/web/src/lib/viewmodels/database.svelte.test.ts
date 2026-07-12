import { describe, expect, it, vi } from 'vitest';
import * as Y from 'yjs';

import { applyFilters, createDatabase, sortRows, type Property } from './database.svelte';

vi.stubGlobal('crypto', {
	randomUUID: () => `${Math.random().toString(16).slice(2)}-x-x-x-x`
});

describe('database view-model', () => {
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
});
