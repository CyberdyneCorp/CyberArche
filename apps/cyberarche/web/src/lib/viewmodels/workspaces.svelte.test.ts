import { beforeEach, describe, expect, it, vi } from 'vitest';

import { createWorkspaces } from './workspaces.svelte';

const WORKSPACE = (id: string, name = `Workspace ${id}`) => ({
	id,
	name,
	created_by: 'alice',
	created_at: '2026-01-01T00:00:00Z',
	rag_project_slug: null
});

/** Routes fetch by URL+method so the VM's real request shapes are exercised. */
function routedFetch(routes: Record<string, unknown>) {
	return vi.fn(async (url: string, init?: RequestInit) => {
		const key = `${init?.method ?? 'GET'} ${url}`;
		const body = routes[key];
		if (body === undefined) throw new Error(`unrouted: ${key}`);
		return { ok: true, status: 200, json: async () => body };
	}) as unknown as typeof fetch;
}

describe('workspaces ViewModel', () => {
	beforeEach(() => vi.restoreAllMocks());

	it('starts empty and not loaded', () => {
		const vm = createWorkspaces();

		expect(vm.items).toEqual([]);
		expect(vm.loaded).toBe(false);
	});

	it('load fetches the list and flips loaded', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({ 'GET /api/v1/workspaces': [WORKSPACE('ws-1'), WORKSPACE('ws-2')] })
		);
		const vm = createWorkspaces();
		await vm.load();

		expect(vm.items.map((w) => w.id)).toEqual(['ws-1', 'ws-2']);
		expect(vm.loaded).toBe(true);
	});

	it('byId finds a loaded workspace and misses unknown ids', async () => {
		vi.stubGlobal('fetch', routedFetch({ 'GET /api/v1/workspaces': [WORKSPACE('ws-1')] }));
		const vm = createWorkspaces();
		await vm.load();

		expect(vm.byId('ws-1')?.name).toBe('Workspace ws-1');
		expect(vm.byId('nope')).toBeUndefined();
	});

	it('create appends the new workspace and returns it', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/workspaces': [WORKSPACE('ws-1')],
				'POST /api/v1/workspaces': WORKSPACE('ws-2', 'Fresh')
			})
		);
		const vm = createWorkspaces();
		await vm.load();

		const created = await vm.create('Fresh');

		expect(created.name).toBe('Fresh');
		expect(vm.items.map((w) => w.id)).toEqual(['ws-1', 'ws-2']);
	});

	it('a failed load rejects and leaves the VM unloaded', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async () => ({
				ok: false,
				status: 500,
				json: async () => ({ detail: 'boom' })
			})) as unknown as typeof fetch
		);
		const vm = createWorkspaces();

		await expect(vm.load()).rejects.toMatchObject({ status: 500 });
		expect(vm.loaded).toBe(false);
		expect(vm.items).toEqual([]);
	});

	it('a failed create rejects without appending', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async (_url: string, init?: RequestInit) => {
				if ((init?.method ?? 'GET') === 'POST') {
					return { ok: false, status: 403, json: async () => ({ detail: 'nope' }) };
				}
				return { ok: true, status: 200, json: async () => [] };
			}) as unknown as typeof fetch
		);
		const vm = createWorkspaces();
		await vm.load();

		await expect(vm.create('Denied')).rejects.toMatchObject({ status: 403 });
		expect(vm.items).toEqual([]);
	});
});
