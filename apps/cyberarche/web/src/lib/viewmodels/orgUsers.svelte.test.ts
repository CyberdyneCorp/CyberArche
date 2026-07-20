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

	describe('loadAll mode', () => {
		const USERS = (prefix: string, count: number) =>
			Array.from({ length: count }, (_, i) => USER(`${prefix}${i}`));

		const allUrl = (search: string, page: number) =>
			`/api/v1/org/users?search=${search}&page=${page}&page_size=200`;

		const allPage = (users: ReturnType<typeof USER>[], total: number, page: number) => ({
			body: { users, total, page, page_size: 200 }
		});

		it('load pages through the directory until total is reached', async () => {
			const fetchMock = routedFetch({
				[allUrl('', 1)]: allPage(USERS('a', 200), 250, 1),
				[allUrl('', 2)]: allPage(USERS('b', 50), 250, 2)
			});
			vi.stubGlobal('fetch', fetchMock);
			const vm = createOrgUsers({ loadAll: true });

			await vm.load();

			expect(fetchMock).toHaveBeenCalledTimes(2);
			expect(vm.users).toHaveLength(250);
			expect(vm.users[0].id).toBe('a0');
			expect(vm.users[249].id).toBe('b49');
			expect(vm.total).toBe(250);
			expect(vm.truncated).toBe(false);
			expect(vm.loading).toBe(false);
		});

		it('a single page suffices when total fits in one request', async () => {
			const fetchMock = routedFetch({ [allUrl('', 1)]: allPage(USERS('a', 3), 3, 1) });
			vi.stubGlobal('fetch', fetchMock);
			const vm = createOrgUsers({ loadAll: true });

			await vm.load();

			expect(fetchMock).toHaveBeenCalledTimes(1);
			expect(vm.users).toHaveLength(3);
		});

		it('caps at 1000 users and reports truncation', async () => {
			const routes: Record<string, { body: unknown }> = {};
			for (let page = 1; page <= 5; page += 1) {
				routes[allUrl('', page)] = allPage(USERS(`p${page}-`, 200), 1200, page);
			}
			const fetchMock = routedFetch(routes);
			vi.stubGlobal('fetch', fetchMock);
			const vm = createOrgUsers({ loadAll: true });

			await vm.load();

			expect(fetchMock).toHaveBeenCalledTimes(5);
			expect(vm.users).toHaveLength(1000);
			expect(vm.total).toBe(1200);
			expect(vm.truncated).toBe(true);
		});

		it('stops paging when the server returns an empty page early', async () => {
			const fetchMock = routedFetch({
				[allUrl('', 1)]: allPage(USERS('a', 200), 500, 1),
				[allUrl('', 2)]: allPage([], 500, 2)
			});
			vi.stubGlobal('fetch', fetchMock);
			const vm = createOrgUsers({ loadAll: true });

			await vm.load();

			expect(fetchMock).toHaveBeenCalledTimes(2);
			expect(vm.users).toHaveLength(200);
		});

		it('debounced search pages with the search param', async () => {
			const fetchMock = routedFetch({ [allUrl('ada', 1)]: allPage([USER('ada')], 1, 1) });
			vi.stubGlobal('fetch', fetchMock);
			const vm = createOrgUsers({ loadAll: true });

			vm.search(' ada ');
			await vi.advanceTimersByTimeAsync(250);

			expect(fetchMock).toHaveBeenCalledTimes(1);
			expect(vm.users.map((u) => u.id)).toEqual(['ada']);
		});
	});
});
