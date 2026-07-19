import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { createOrgUsers } from './orgUsers.svelte';

const USER = (id: string, email: string | null = `${id}@acme.dev`) => ({
	id,
	email,
	avatar_url: null,
	is_active: true
});

const PAGE = (users: ReturnType<typeof USER>[]) => ({
	users,
	total: users.length,
	page: 1,
	page_size: 50
});

const url = (search: string) => `/api/v1/org/users?search=${search}&page=1&page_size=50`;

/** Routes fetch by URL; a route may carry an error status. */
function routedFetch(routes: Record<string, { status?: number; body?: unknown }>) {
	return vi.fn(async (requested: string) => {
		const route = routes[requested];
		if (!route) throw new Error(`unrouted: ${requested}`);
		const status = route.status ?? 200;
		return {
			ok: status < 400,
			status,
			json: async () => route.body ?? { error: 'Error', detail: 'boom' }
		};
	}) as unknown as typeof fetch;
}

describe('orgUsers ViewModel', () => {
	beforeEach(() => {
		vi.useFakeTimers();
	});
	afterEach(() => {
		vi.useRealTimers();
		vi.restoreAllMocks();
	});

	it('starts empty, not loading, and available', () => {
		const vm = createOrgUsers();

		expect(vm.users).toEqual([]);
		expect(vm.total).toBe(0);
		expect(vm.loading).toBe(false);
		expect(vm.unavailable).toBe(false);
		expect(vm.error).toBeNull();
	});

	it('load fetches the first page immediately', async () => {
		const fetchMock = routedFetch({ [url('')]: { body: PAGE([USER('ada')]) } });
		vi.stubGlobal('fetch', fetchMock);
		const vm = createOrgUsers();

		const pending = vm.load();
		expect(vm.loading).toBe(true);
		await pending;

		expect(vm.users.map((u) => u.id)).toEqual(['ada']);
		expect(vm.total).toBe(1);
		expect(vm.loading).toBe(false);
		expect(fetchMock).toHaveBeenCalledTimes(1);
	});

	it('search debounces keystrokes into a single trimmed request', async () => {
		const fetchMock = routedFetch({ [url('ada')]: { body: PAGE([USER('ada')]) } });
		vi.stubGlobal('fetch', fetchMock);
		const vm = createOrgUsers();

		vm.search('a');
		vm.search('ad');
		vm.search(' ada ');
		expect(vm.loading).toBe(true);
		expect(fetchMock).not.toHaveBeenCalled();

		await vi.advanceTimersByTimeAsync(250);

		expect(fetchMock).toHaveBeenCalledTimes(1);
		expect(vm.users.map((u) => u.id)).toEqual(['ada']);
		expect(vm.loading).toBe(false);
	});

	it('a 503 flips unavailable so views fall back to raw-id entry', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({ [url('')]: { status: 503, body: { error: 'UpstreamUnavailable', detail: 'down' } } })
		);
		const vm = createOrgUsers();
		await vm.load();

		expect(vm.unavailable).toBe(true);
		expect(vm.users).toEqual([]);
		expect(vm.error).toBeNull();
		expect(vm.loading).toBe(false);
	});

	it('a later success clears unavailable', async () => {
		vi.stubGlobal('fetch', routedFetch({ [url('')]: { status: 503, body: {} } }));
		const vm = createOrgUsers();
		await vm.load();
		expect(vm.unavailable).toBe(true);

		vi.stubGlobal('fetch', routedFetch({ [url('ada')]: { body: PAGE([USER('ada')]) } }));
		vm.search('ada');
		await vi.advanceTimersByTimeAsync(250);

		expect(vm.unavailable).toBe(false);
		expect(vm.users.map((u) => u.id)).toEqual(['ada']);
	});

	it('non-503 failures surface an error without flagging unavailable', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({ [url('')]: { status: 500, body: { error: 'Internal', detail: 'boom' } } })
		);
		const vm = createOrgUsers();
		await vm.load();

		expect(vm.unavailable).toBe(false);
		expect(vm.error).toMatch(/boom/);
		expect(vm.users).toEqual([]);
	});

	it('ignores an out-of-order response from a superseded search', async () => {
		const resolvers: Array<(page: unknown) => void> = [];
		vi.stubGlobal(
			'fetch',
			vi.fn(
				(requested: string) =>
					new Promise((resolve) => {
						resolvers.push((page) => resolve({ ok: true, status: 200, json: async () => page }));
						void requested;
					})
			) as unknown as typeof fetch
		);
		const vm = createOrgUsers();

		vm.search('a');
		await vi.advanceTimersByTimeAsync(250);
		vm.search('ab');
		await vi.advanceTimersByTimeAsync(250);
		expect(resolvers).toHaveLength(2);

		resolvers[1](PAGE([USER('winner')]));
		await vi.advanceTimersByTimeAsync(0);
		resolvers[0](PAGE([USER('stale')]));
		await vi.advanceTimersByTimeAsync(0);

		expect(vm.users.map((u) => u.id)).toEqual(['winner']);
		expect(vm.loading).toBe(false);
	});
});
