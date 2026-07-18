import { flushSync, mount, unmount } from 'svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { dayKey } from '$lib/viewmodels/calendar';
import CollectionCalendar from './CollectionCalendar.svelte';

const DUE = { id: 'due', name: 'Due', type: 'date', options: [] };

const row = (id: string, due?: string) => ({
	id,
	workspace_id: 'ws-1',
	title: `Row ${id}`,
	collection_id: 'c1',
	properties: due === undefined ? {} : { due },
	created_at: '',
	updated_at: ''
});

/** A day in the currently-displayed month (the component anchors on today). */
function midCurrentMonth(): string {
	const now = new Date();
	return dayKey(new Date(now.getFullYear(), now.getMonth(), 15));
}

function fakeVm(overrides: Record<string, unknown> = {}) {
	return {
		rows: [],
		properties: [DUE],
		dateProperties: [DUE],
		dateByProperty: DUE,
		setDateBy: vi.fn(),
		...overrides
	};
}

describe('CollectionCalendar component', () => {
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
		instance = mount(CollectionCalendar, { target, props: { vm: vm as never, onOpenRow } });
		flushSync();
	}

	it('prompts to pick a date property when unset and choosing calls setDateBy', () => {
		const vm = fakeVm({ dateByProperty: undefined });
		render(vm);
		expect(target.querySelector('[data-testid="calendar-dateby-prompt"]')).not.toBeNull();
		const select = target.querySelector<HTMLSelectElement>(
			'[data-testid="calendar-dateby-select"]'
		)!;
		select.value = 'due';
		select.dispatchEvent(new Event('change', { bubbles: true }));
		expect(vm.setDateBy).toHaveBeenCalledWith('due');
	});

	it('renders a dated row as a chip on its day and opens it on click', () => {
		const onOpenRow = vi.fn();
		const vm = fakeVm({ rows: [row('r1', midCurrentMonth())] });
		render(vm, onOpenRow);
		const chip = target.querySelector<HTMLButtonElement>('[data-testid="calendar-chip"]')!;
		expect(chip.textContent?.trim()).toBe('Row r1');
		chip.dispatchEvent(new Event('click', { bubbles: true }));
		expect(onOpenRow).toHaveBeenCalledWith('r1');
	});

	it('prev and next move the displayed month', () => {
		const vm = fakeVm();
		render(vm);
		const title = () =>
			target.querySelector('[data-testid="calendar-title"]')?.textContent?.trim();
		const initial = title();

		target
			.querySelector('[data-testid="calendar-next"]')!
			.dispatchEvent(new Event('click', { bubbles: true }));
		flushSync();
		expect(title()).not.toBe(initial);

		target
			.querySelector('[data-testid="calendar-prev"]')!
			.dispatchEvent(new Event('click', { bubbles: true }));
		flushSync();
		expect(title()).toBe(initial);
	});

	it('lists undated rows in the unscheduled section', () => {
		const vm = fakeVm({ rows: [row('r1', undefined)] });
		render(vm);
		const section = target.querySelector('[data-testid="calendar-unscheduled"]')!;
		expect(section).not.toBeNull();
		expect(
			section.querySelector('[data-testid="calendar-unscheduled-count"]')?.textContent
		).toBe('1');
		expect(
			section.querySelector('[data-testid="calendar-unscheduled-chip"]')?.textContent?.trim()
		).toBe('Row r1');
	});
});
