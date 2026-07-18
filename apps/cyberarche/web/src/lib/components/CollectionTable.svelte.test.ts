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
		rename: vi.fn(),
		selectView: vi.fn(),
		addRow: vi.fn(),
		setCell: vi.fn(),
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

	it('renders a placeholder for non-table view kinds (the future-view seam)', () => {
		const vm = fakeVm({
			currentView: { id: 'v2', name: 'Board', kind: 'board', filters: [], sorts: [], group_by: null, date_by: null }
		});
		render(vm);
		expect(target.querySelector('.placeholder')?.textContent).toContain('board');
		expect(target.querySelector('[data-testid="collection-table"]')).toBeNull();
	});
});
