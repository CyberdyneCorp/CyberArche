import { flushSync, mount, unmount } from 'svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import CollectionTable from './CollectionTable.svelte';

function fakeVm(overrides: Record<string, unknown> = {}) {
	return {
		collection: {
			id: 'c1',
			workspace_id: 'ws-1',
			name: 'Tasks',
			properties: [],
			views: [{ id: 'v1', name: 'Table', kind: 'table' }],
			created_at: ''
		},
		rows: [
			{
				id: 'r1',
				workspace_id: 'ws-1',
				title: 'First',
				collection_id: 'c1',
				properties: { done: false, status: 'todo' },
				created_at: '',
				updated_at: ''
			}
		],
		properties: [
			{ id: 'done', name: 'Done', type: 'checkbox', options: [] },
			{ id: 'status', name: 'Status', type: 'select', options: ['todo', 'done'] }
		],
		currentView: { id: 'v1', name: 'Table', kind: 'table', filters: [], sorts: [], group_by: null, date_by: null },
		busy: false,
		error: null,
		filters: [],
		sorts: [],
		activeFilterCount: 0,
		activeSortCount: 0,
		groupByProperty: undefined,
		selectProperties: [{ id: 'status', name: 'Status', type: 'select', options: ['todo', 'done'] }],
		dateProperties: [],
		dateByProperty: undefined,
		setDateBy: vi.fn(),
		rename: vi.fn(),
		selectView: vi.fn(),
		createViewOfKind: vi.fn(),
		addRow: vi.fn(),
		setCell: vi.fn(),
		setRelation: vi.fn(),
		relatedTitle: (id: string) => id,
		loadRelationRows: vi.fn(async () => []),
		loadWorkspaceCollections: vi.fn(async () => []),
		loadCollectionProperties: vi.fn(async () => []),
		relationProperties: [],
		selectedIds: [],
		selectedCount: 0,
		isSelected: () => false,
		toggleRow: vi.fn(),
		toggleAll: vi.fn(),
		clearSelection: vi.fn(),
		bulkDelete: vi.fn(),
		bulkSet: vi.fn(),
		setRowGroup: vi.fn(),
		setBoardGroupBy: vi.fn(),
		renameRow: vi.fn(),
		addProperty: vi.fn(),
		addFilter: vi.fn(),
		updateFilter: vi.fn(),
		removeFilter: vi.fn(),
		addSort: vi.fn(),
		updateSort: vi.fn(),
		removeSort: vi.fn(),
		moveSort: vi.fn(),
		...overrides
	};
}

describe('CollectionTable component', () => {
	let target: HTMLElement;
	let instance: Record<string, unknown> | null = null;

	beforeEach(() => {
		target = document.createElement('div');
		document.body.appendChild(target);
	});
	afterEach(() => {
		if (instance) unmount(instance);
		instance = null;
		target.remove();
	});

	function render(vm: ReturnType<typeof fakeVm>, onOpenRow = vi.fn()) {
		instance = mount(CollectionTable, {
			target,
			props: { vm: vm as never, onOpenRow }
		});
		flushSync();
	}

	function renderReadOnly(vm: ReturnType<typeof fakeVm>, onOpenRow = vi.fn()) {
		instance = mount(CollectionTable, {
			target,
			props: { vm: vm as never, onOpenRow, readOnly: true }
		});
		flushSync();
	}

	it('renders a column per schema property plus the title column', () => {
		const vm = fakeVm();
		render(vm);
		const headers = [...target.querySelectorAll('[data-testid="column-header"]')].map(
			(h) => h.textContent
		);
		expect(headers).toEqual(['Done', 'Status']);
		expect(target.querySelector('.title-col')?.textContent).toBe('Name');
		expect(target.querySelectorAll('[data-testid="collection-row"]').length).toBe(1);
	});

	it('editing a checkbox cell calls setCell with a boolean', () => {
		const vm = fakeVm();
		render(vm);
		const checkbox = target.querySelector<HTMLInputElement>('[data-testid="cell-checkbox"]')!;
		checkbox.checked = true;
		checkbox.dispatchEvent(new Event('change', { bubbles: true }));
		expect(vm.setCell).toHaveBeenCalledWith('r1', 'done', true);
	});

	it('editing a select cell calls setCell with the option', () => {
		const vm = fakeVm();
		render(vm);
		const select = target.querySelector<HTMLSelectElement>('[data-testid="cell-select"]')!;
		select.value = 'done';
		select.dispatchEvent(new Event('change', { bubbles: true }));
		expect(vm.setCell).toHaveBeenCalledWith('r1', 'status', 'done');
	});

	it('renders a formula cell read-only with the computed value and no editor', () => {
		const vm = fakeVm({
			properties: [{ id: 'total', name: 'Total', type: 'formula', options: [], formula: 'x' }],
			rows: [
				{
					id: 'r1',
					workspace_id: 'ws-1',
					title: 'First',
					collection_id: 'c1',
					properties: { total: 30 },
					created_at: '',
					updated_at: ''
				}
			]
		});
		render(vm);
		const cell = target.querySelector('[data-testid="cell-formula"]')!;
		expect(cell.textContent).toBe('30');
		// A formula column is not editable: no input control is rendered for it.
		expect(target.querySelector('[data-testid="cell-number"]')).toBeNull();
		expect(target.querySelector('[data-testid="cell-text"]')).toBeNull();
		// The header carries the ƒ marker.
		expect(target.querySelector('[data-testid="column-header"]')?.textContent).toContain('ƒ');
		// Nothing was written for the formula column.
		expect(vm.setCell).not.toHaveBeenCalled();
	});

	it('shows a formula expression input when the formula type is chosen and passes it', () => {
		const vm = fakeVm();
		render(vm);
		target.querySelector<HTMLButtonElement>('[data-testid="add-property"]')!.click();
		flushSync();
		const name = target.querySelector<HTMLInputElement>('[data-testid="prop-name"]')!;
		name.value = 'Total';
		name.dispatchEvent(new Event('input', { bubbles: true }));
		const type = target.querySelector<HTMLSelectElement>('[data-testid="prop-type"]')!;
		type.value = 'formula';
		type.dispatchEvent(new Event('change', { bubbles: true }));
		flushSync();
		const formula = target.querySelector<HTMLInputElement>('[data-testid="prop-formula"]')!;
		expect(formula).not.toBeNull();
		formula.value = 'prop("Price") * prop("Qty")';
		formula.dispatchEvent(new Event('input', { bubbles: true }));
		target.querySelector<HTMLFormElement>('[data-testid="add-property-form"]')!.dispatchEvent(
			new Event('submit', { bubbles: true, cancelable: true })
		);
		expect(vm.addProperty).toHaveBeenCalledWith(
			'Total',
			'formula',
			[],
			'prop("Price") * prop("Qty")',
			{},
			-1
		);
	});

	it('shows a reminder select for a date property and passes the lead time', () => {
		const vm = fakeVm();
		render(vm);
		target.querySelector<HTMLButtonElement>('[data-testid="add-property"]')!.click();
		flushSync();
		const name = target.querySelector<HTMLInputElement>('[data-testid="prop-name"]')!;
		name.value = 'Due';
		name.dispatchEvent(new Event('input', { bubbles: true }));
		const type = target.querySelector<HTMLSelectElement>('[data-testid="prop-type"]')!;
		type.value = 'date';
		type.dispatchEvent(new Event('change', { bubbles: true }));
		flushSync();
		const reminder = target.querySelector<HTMLSelectElement>('[data-testid="prop-reminder"]')!;
		expect(reminder).not.toBeNull();
		reminder.value = '1440';
		reminder.dispatchEvent(new Event('change', { bubbles: true }));
		flushSync();
		target.querySelector<HTMLFormElement>('[data-testid="add-property-form"]')!.dispatchEvent(
			new Event('submit', { bubbles: true, cancelable: true })
		);
		expect(vm.addProperty).toHaveBeenCalledWith('Due', 'date', [], '', {}, 1440);
	});

	it('renders a relation cell as chips resolved by relatedTitle, with a toggle picker', async () => {
		const vm = fakeVm({
			properties: [
				{ id: 'rel', name: 'Tasks', type: 'relation', options: [], relation_collection_id: 'c2' }
			],
			rows: [
				{
					id: 'r1',
					workspace_id: 'ws-1',
					title: 'First',
					collection_id: 'c1',
					properties: { rel: ['t1'] },
					created_at: '',
					updated_at: ''
				}
			],
			relatedTitle: (id: string) => (id === 't1' ? 'Design' : 'Untitled'),
			loadRelationRows: vi.fn(async () => [
				{ id: 't1', title: 'Design' },
				{ id: 't2', title: 'Build' }
			])
		});
		render(vm);
		// The linked row shows by title, not id.
		expect(target.querySelector('[data-testid="relation-chip"]')?.textContent).toBe('Design');
		// Header carries the relation marker.
		expect(target.querySelector('[data-testid="column-header"]')?.textContent).toContain('🔗');

		// Open the picker (loads the target collection's rows) and toggle a link.
		target.querySelector<HTMLButtonElement>('[data-testid="relation-edit"]')!.click();
		await Promise.resolve();
		flushSync();
		expect(vm.loadRelationRows).toHaveBeenCalledWith('c2');
		const options = target.querySelectorAll<HTMLInputElement>('[data-testid="relation-option"]');
		expect(options.length).toBe(2);
		// Toggle the second (unlinked) row on -> setRelation with both ids.
		options[1].dispatchEvent(new Event('change', { bubbles: true }));
		expect(vm.setRelation).toHaveBeenCalledWith('r1', 'rel', ['t1', 't2']);
	});

	it('renders a rollup cell read-only with the computed value and no editor', () => {
		const vm = fakeVm({
			properties: [
				{
					id: 'roll',
					name: 'Task count',
					type: 'rollup',
					options: [],
					rollup_relation_property_id: 'rel',
					rollup_target_property_id: '__title__',
					rollup_function: 'count'
				}
			],
			rows: [
				{
					id: 'r1',
					workspace_id: 'ws-1',
					title: 'First',
					collection_id: 'c1',
					properties: { roll: 3 },
					created_at: '',
					updated_at: ''
				}
			]
		});
		render(vm);
		expect(target.querySelector('[data-testid="cell-rollup"]')?.textContent).toBe('3');
		expect(target.querySelector('[data-testid="column-header"]')?.textContent).toContain('Σ');
		// No editor is rendered and nothing is written for a rollup column.
		expect(target.querySelector('[data-testid="cell-number"]')).toBeNull();
		expect(vm.setCell).not.toHaveBeenCalled();
	});

	it('add row button calls vm.addRow', () => {
		const vm = fakeVm();
		render(vm);
		target.querySelector<HTMLButtonElement>('[data-testid="add-row"]')!.click();
		expect(vm.addRow).toHaveBeenCalled();
	});

	it('opening a row invokes the onOpenRow callback', () => {
		const vm = fakeVm();
		const onOpenRow = vi.fn();
		render(vm, onOpenRow);
		target.querySelector<HTMLButtonElement>('[data-testid="open-row"]')!.click();
		expect(onOpenRow).toHaveBeenCalledWith('r1');
	});

	it('adding a filter rule calls vm.addFilter', () => {
		const vm = fakeVm();
		render(vm);
		target.querySelector<HTMLButtonElement>('[data-testid="filter-button"]')!.click();
		flushSync();
		target.querySelector<HTMLButtonElement>('[data-testid="add-filter"]')!.click();
		expect(vm.addFilter).toHaveBeenCalled();
	});

	it('the filter panel renders a value control matching the property type', () => {
		const vm = fakeVm({
			properties: [{ id: 'age', name: 'Age', type: 'number', options: [] }],
			filters: [{ property_id: 'age', op: 'gt', value: '5' }],
			activeFilterCount: 1
		});
		render(vm);
		target.querySelector<HTMLButtonElement>('[data-testid="filter-button"]')!.click();
		flushSync();
		const value = target.querySelector<HTMLInputElement>('[data-testid="filter-value"]')!;
		expect(value.type).toBe('number');
		// The operator picker only offers number-appropriate operators (no `contains`).
		const ops = [...target.querySelectorAll('[data-testid="filter-op"] option')].map(
			(o) => o.getAttribute('value')
		);
		expect(ops).toContain('gt');
		expect(ops).not.toContain('contains');
	});

	it('shows the empty state when rows are empty due to active filters', () => {
		const vm = fakeVm({ rows: [], activeFilterCount: 1 });
		render(vm);
		expect(target.querySelector('[data-testid="no-rows"]')?.textContent).toContain(
			'No rows match'
		);
	});

	it('renders the calendar surface for a calendar view', () => {
		const vm = fakeVm({
			currentView: { id: 'v4', name: 'Cal', kind: 'calendar', filters: [], sorts: [], group_by: null, date_by: null }
		});
		render(vm);
		// No date_by property configured yet, so the calendar prompts to pick one.
		expect(target.querySelector('[data-testid="calendar-dateby-prompt"]')).not.toBeNull();
		expect(target.querySelector('[data-testid="collection-table"]')).toBeNull();
	});

	it('renders the board surface for a board view', () => {
		const vm = fakeVm({
			currentView: { id: 'v2', name: 'Board', kind: 'board', filters: [], sorts: [], group_by: null, date_by: null }
		});
		render(vm);
		// No group_by yet, so the board prompts for a group-by property.
		expect(target.querySelector('[data-testid="board-groupby-prompt"]')).not.toBeNull();
		expect(target.querySelector('[data-testid="collection-table"]')).toBeNull();
	});

	it('renders the gallery surface for a gallery view', () => {
		const vm = fakeVm({
			currentView: { id: 'v3', name: 'Gallery', kind: 'gallery', filters: [], sorts: [], group_by: null, date_by: null }
		});
		render(vm);
		expect(target.querySelector('[data-testid="collection-gallery"]')).not.toBeNull();
		expect(target.querySelector('[data-testid="collection-table"]')).toBeNull();
	});

	it('adding a view submits the name and kind to createViewOfKind', () => {
		const vm = fakeVm();
		render(vm);
		target.querySelector<HTMLButtonElement>('[data-testid="add-view"]')!.click();
		flushSync();
		const name = target.querySelector<HTMLInputElement>('[data-testid="view-name"]')!;
		name.value = 'My board';
		name.dispatchEvent(new Event('input', { bubbles: true }));
		const kind = target.querySelector<HTMLSelectElement>('[data-testid="view-kind"]')!;
		kind.value = 'board';
		kind.dispatchEvent(new Event('change', { bubbles: true }));
		target.querySelector<HTMLFormElement>('[data-testid="add-view-form"]')!.dispatchEvent(
			new Event('submit', { bubbles: true, cancelable: true })
		);
		expect(vm.createViewOfKind).toHaveBeenCalledWith('My board', 'board');
	});

	it('renders a select-all header checkbox and a per-row checkbox that toggles', () => {
		const vm = fakeVm();
		render(vm);
		expect(target.querySelector('[data-testid="select-all"]')).not.toBeNull();
		const rowBox = target.querySelector<HTMLInputElement>('[data-testid="row-select"]')!;
		rowBox.click();
		expect(vm.toggleRow).toHaveBeenCalledWith('r1');
	});

	it('read-only mode hides add-row, add-property, add-view and bulk selection', () => {
		const vm = fakeVm({ selectedCount: 2, isSelected: () => true });
		renderReadOnly(vm);
		// Editing affordances are gone.
		expect(target.querySelector('[data-testid="add-row"]')).toBeNull();
		expect(target.querySelector('[data-testid="add-property"]')).toBeNull();
		expect(target.querySelector('[data-testid="add-view"]')).toBeNull();
		expect(target.querySelector('[data-testid="select-all"]')).toBeNull();
		expect(target.querySelector('[data-testid="row-select"]')).toBeNull();
		// The bulk bar stays hidden even though rows are "selected".
		expect(target.querySelector('[data-testid="bulk-bar"]')).toBeNull();
		// Cells render as read-only values, not editors.
		expect(target.querySelector('[data-testid="cell-readonly"]')).not.toBeNull();
		expect(target.querySelector('[data-testid="cell-checkbox"]')).toBeNull();
		expect(target.querySelector('[data-testid="cell-select"]')).toBeNull();
		// Rows can still be opened as pages.
		expect(target.querySelector('[data-testid="open-row"]')).not.toBeNull();
	});

	it('shows the bulk action bar only when rows are selected', () => {
		const hidden = fakeVm();
		render(hidden);
		expect(target.querySelector('[data-testid="bulk-bar"]')).toBeNull();
		unmount(instance!);
		instance = null;

		const shown = fakeVm({ selectedCount: 2, isSelected: () => true });
		render(shown);
		expect(target.querySelector('[data-testid="bulk-bar"]')).not.toBeNull();
		expect(target.querySelector('[data-testid="bulk-count"]')!.textContent).toContain('2 selected');
	});
});
