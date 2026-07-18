import { flushSync, mount, unmount } from 'svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import CollectionGallery from './CollectionGallery.svelte';

const row = (id: string) => ({
	id,
	workspace_id: 'ws-1',
	title: `Row ${id}`,
	collection_id: 'c1',
	properties: { status: 'todo' },
	created_at: '',
	updated_at: ''
});

function fakeVm(overrides: Record<string, unknown> = {}) {
	return {
		rows: [row('r1'), row('r2')],
		properties: [{ id: 'status', name: 'Status', type: 'select', options: ['todo', 'done'] }],
		...overrides
	};
}

describe('CollectionGallery component', () => {
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
		instance = mount(CollectionGallery, { target, props: { vm: vm as never, onOpenRow } });
		flushSync();
	}

	it('renders a card per row', () => {
		const vm = fakeVm();
		render(vm);
		expect(target.querySelector('[data-testid="collection-gallery"]')).not.toBeNull();
		expect(target.querySelectorAll('[data-testid="collection-card"]').length).toBe(2);
	});

	it('clicking a card navigates via onOpenRow', () => {
		const vm = fakeVm();
		const onOpenRow = vi.fn();
		render(vm, onOpenRow);
		target.querySelector<HTMLButtonElement>('[data-testid="card-title"]')!.click();
		expect(onOpenRow).toHaveBeenCalledWith('r1');
	});

	it('shows the empty state when there are no rows', () => {
		const vm = fakeVm({ rows: [] });
		render(vm);
		expect(target.querySelector('[data-testid="gallery-empty"]')).not.toBeNull();
		expect(target.querySelector('[data-testid="collection-gallery"]')).toBeNull();
	});
});
