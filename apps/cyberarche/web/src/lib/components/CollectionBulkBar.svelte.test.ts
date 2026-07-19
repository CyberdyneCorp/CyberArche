import { flushSync, mount, unmount } from 'svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import CollectionBulkBar from './CollectionBulkBar.svelte';
import { dialogs } from '$lib/viewmodels/dialogs.svelte';

function fakeVm(overrides: Record<string, unknown> = {}) {
	return {
		selectedCount: 2,
		properties: [
			{ id: 'status', name: 'Status', type: 'select', options: ['todo', 'done'] },
			{ id: 'score', name: 'Score', type: 'number', options: [] },
			{ id: 'fx', name: 'Total', type: 'formula', options: [] }
		],
		bulkSet: vi.fn(),
		bulkDelete: vi.fn(),
		clearSelection: vi.fn(),
		...overrides
	};
}

describe('CollectionBulkBar component', () => {
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
		vi.restoreAllMocks();
	});

	function render(vm: ReturnType<typeof fakeVm>) {
		instance = mount(CollectionBulkBar, { target, props: { vm: vm as never } });
		flushSync();
	}

	it('lists only simple settable properties (excludes formula/rollup)', () => {
		render(fakeVm());
		const options = [
			...target.querySelectorAll<HTMLOptionElement>('[data-testid="bulk-property"] option')
		].map((o) => o.value);
		// The placeholder plus the two settable props; the formula is excluded.
		expect(options).toEqual(['', 'status', 'score']);
	});

	it('picking a select property then Set calls bulkSet with the chosen value', () => {
		const vm = fakeVm();
		render(vm);
		const picker = target.querySelector<HTMLSelectElement>('[data-testid="bulk-property"]')!;
		picker.value = 'status';
		picker.dispatchEvent(new Event('change', { bubbles: true }));
		flushSync();

		const valueSel = target.querySelector<HTMLSelectElement>('[data-testid="bulk-value-select"]')!;
		valueSel.value = 'done';
		valueSel.dispatchEvent(new Event('change', { bubbles: true }));
		flushSync();

		target.querySelector<HTMLButtonElement>('[data-testid="bulk-set"]')!.click();
		expect(vm.bulkSet).toHaveBeenCalledWith('status', 'done');
	});

	it('Delete confirms via dialogs then calls bulkDelete', async () => {
		const vm = fakeVm();
		const confirm = vi.spyOn(dialogs, 'confirm').mockResolvedValue(true);
		render(vm);
		target.querySelector<HTMLButtonElement>('[data-testid="bulk-delete"]')!.click();
		await Promise.resolve();
		await Promise.resolve();
		expect(confirm).toHaveBeenCalled();
		expect(vm.bulkDelete).toHaveBeenCalled();
	});

	it('Delete does nothing when the confirm is dismissed', async () => {
		const vm = fakeVm();
		vi.spyOn(dialogs, 'confirm').mockResolvedValue(false);
		render(vm);
		target.querySelector<HTMLButtonElement>('[data-testid="bulk-delete"]')!.click();
		await Promise.resolve();
		await Promise.resolve();
		expect(vm.bulkDelete).not.toHaveBeenCalled();
	});

	it('Clear calls clearSelection', () => {
		const vm = fakeVm();
		render(vm);
		target.querySelector<HTMLButtonElement>('[data-testid="bulk-clear"]')!.click();
		expect(vm.clearSelection).toHaveBeenCalled();
	});
});
