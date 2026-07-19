import { flushSync, mount, unmount } from 'svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import * as collectionsApi from '$lib/api/collections';
import CollectionViewBlock from './CollectionViewBlock.svelte';

vi.mock('$app/navigation', () => ({ goto: vi.fn() }));
vi.mock('$app/state', () => ({ page: { params: { workspaceId: 'ws-1' } } }));

vi.mock('$lib/api/collections', () => ({
	createCollection: vi.fn(),
	getCollection: vi.fn(),
	queryView: vi.fn(),
	listCollections: vi.fn()
}));

const api = vi.mocked(collectionsApi);

function block(data: Record<string, unknown>) {
	return { id: 'b1', type: 'collection_view', data };
}

function fakeEditor(readOnly: boolean) {
	return { readOnly, updateData: vi.fn() };
}

/** Let queued microtasks (createCollection / load) settle. */
async function settle() {
	await Promise.resolve();
	await Promise.resolve();
	flushSync();
}

describe('CollectionViewBlock', () => {
	let target: HTMLElement;
	let instance: Record<string, unknown> | null = null;

	beforeEach(() => {
		vi.clearAllMocks();
		target = document.createElement('div');
		document.body.appendChild(target);
	});
	afterEach(() => {
		if (instance) unmount(instance);
		instance = null;
		target.remove();
	});

	function render(props: { block: ReturnType<typeof block>; editor: unknown }) {
		instance = mount(CollectionViewBlock, { target, props: props as never });
		flushSync();
	}

	it('self-initialises once: creates a collection and persists its ids', async () => {
		api.createCollection.mockResolvedValue({
			id: 'c1',
			workspace_id: 'ws-1',
			name: '',
			properties: [],
			views: [{ id: 'v1', name: 'Table', kind: 'table', filters: [], sorts: [], group_by: null, date_by: null }],
			created_at: ''
		});
		const editor = fakeEditor(false);
		render({ block: block({ collection_id: '', view_id: '' }), editor });
		await settle();

		expect(api.createCollection).toHaveBeenCalledTimes(1);
		expect(api.createCollection).toHaveBeenCalledWith('ws-1', '');
		expect(editor.updateData).toHaveBeenCalledTimes(1);
		expect(editor.updateData).toHaveBeenCalledWith('b1', { collection_id: 'c1', view_id: 'v1' });
	});

	it('read-only + empty renders a placeholder and never creates a collection', async () => {
		const editor = fakeEditor(true);
		render({ block: block({ collection_id: '', view_id: '' }), editor });
		await settle();

		expect(api.createCollection).not.toHaveBeenCalled();
		expect(editor.updateData).not.toHaveBeenCalled();
		expect(target.querySelector('[data-testid="collection-empty"]')).not.toBeNull();
	});

	it('with a collection_id, loads the VM and renders the table', async () => {
		api.getCollection.mockResolvedValue({
			id: 'c1',
			workspace_id: 'ws-1',
			name: 'Tasks',
			properties: [{ id: 'p1', name: 'Status', type: 'select', options: ['todo'] }],
			views: [{ id: 'v1', name: 'Table', kind: 'table', filters: [], sorts: [], group_by: null, date_by: null }],
			created_at: ''
		});
		api.queryView.mockResolvedValue({ rows: [], related: [] });

		render({ block: block({ collection_id: 'c1', view_id: 'v1' }), editor: fakeEditor(false) });
		await settle();

		expect(api.createCollection).not.toHaveBeenCalled();
		expect(api.getCollection).toHaveBeenCalledWith('c1');
		expect(api.queryView).toHaveBeenCalledWith('c1', 'v1');
		expect(target.querySelector('[data-testid="collection-view-block"]')).not.toBeNull();
		expect(target.querySelector('[data-testid="collection-table"]')).not.toBeNull();
	});
});
