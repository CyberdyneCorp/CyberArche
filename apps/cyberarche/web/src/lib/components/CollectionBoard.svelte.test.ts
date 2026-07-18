import { flushSync, mount, unmount } from 'svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import CollectionBoard from './CollectionBoard.svelte';

const STATUS = { id: 'status', name: 'Status', type: 'select', options: ['todo', 'done'] };

const row = (id: string, status?: string) => ({
	id,
	workspace_id: 'ws-1',
	title: `Row ${id}`,
	collection_id: 'c1',
	properties: status === undefined ? {} : { status },
	created_at: '',
	updated_at: ''
});

function fakeVm(overrides: Record<string, unknown> = {}) {
	return {
		rows: [row('r1', 'todo'), row('r2', 'done'), row('r3')],
		properties: [STATUS],
		selectProperties: [STATUS],
		groupByProperty: STATUS,
		setRowGroup: vi.fn(),
		setBoardGroupBy: vi.fn(),
		...overrides
	};
}

describe('CollectionBoard component', () => {
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
		instance = mount(CollectionBoard, { target, props: { vm: vm as never, onOpenRow } });
		flushSync();
	}

	it('prompts to pick a group-by property when unset', () => {
		const vm = fakeVm({ groupByProperty: undefined });
		render(vm);
		expect(target.querySelector('[data-testid="board-groupby-prompt"]')).not.toBeNull();
		const select = target.querySelector<HTMLSelectElement>('[data-testid="board-groupby-select"]')!;
		select.value = 'status';
		select.dispatchEvent(new Event('change', { bubbles: true }));
		expect(vm.setBoardGroupBy).toHaveBeenCalledWith('status');
	});

	it('renders a column per option plus Uncategorized with the right cards', () => {
		const vm = fakeVm();
		render(vm);
		const columns = [...target.querySelectorAll('[data-testid="board-column"]')];
		const labels = columns.map((c) => c.querySelector('.col-label')?.textContent);
		expect(labels).toEqual(['todo', 'done', 'Uncategorized']);
		const counts = columns.map((c) =>
			c.querySelector('[data-testid="board-column-count"]')?.textContent
		);
		expect(counts).toEqual(['1', '1', '1']);
		// r3 has no value → lands in the trailing Uncategorized column.
		expect(columns[2].querySelector('[data-testid="card-title"]')?.textContent?.trim()).toBe(
			'Row r3'
		);
	});

	it('shows an empty state for a column with no cards', () => {
		const vm = fakeVm({ rows: [row('r1', 'todo')] });
		render(vm);
		const empties = target.querySelectorAll('[data-testid="board-column-empty"]');
		// The "done" and "Uncategorized" columns are empty.
		expect(empties.length).toBe(2);
	});

	it('moving a card via its menu calls setRowGroup with the target value', () => {
		const vm = fakeVm();
		render(vm);
		const move = target.querySelector<HTMLSelectElement>('[data-testid="board-card-move"]')!;
		move.value = 'done';
		move.dispatchEvent(new Event('change', { bubbles: true }));
		expect(vm.setRowGroup).toHaveBeenCalledWith('r1', 'status', 'done');
	});

	it('moving a card to Uncategorized clears the value (null)', () => {
		const vm = fakeVm();
		render(vm);
		const move = target.querySelector<HTMLSelectElement>('[data-testid="board-card-move"]')!;
		move.value = '';
		move.dispatchEvent(new Event('change', { bubbles: true }));
		expect(vm.setRowGroup).toHaveBeenCalledWith('r1', 'status', null);
	});
});
