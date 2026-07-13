import { beforeEach, describe, expect, it, vi } from 'vitest';

import { createNotifications } from './notifications.svelte';

const NOTIFICATION = (id: string, read = false) => ({
	id,
	kind: 'mention',
	actor_id: 'alice',
	document_id: 'doc-1',
	comment_id: null,
	snippet: `snippet ${id}`,
	read,
	created_at: '2026-01-01T00:00:00Z'
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

function failingFetch() {
	return vi.fn(async () => ({
		ok: false,
		status: 500,
		json: async () => ({ detail: 'boom' })
	})) as unknown as typeof fetch;
}

describe('notifications ViewModel', () => {
	beforeEach(() => vi.restoreAllMocks());

	it('starts empty, with no unread and not loading', () => {
		const vm = createNotifications();

		expect(vm.items).toEqual([]);
		expect(vm.unread).toBe(0);
		expect(vm.loading).toBe(false);
	});

	it('refreshUnread polls the counter', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({ 'GET /api/v1/notifications/unread-count': { count: 4 } })
		);
		const vm = createNotifications();

		await vm.refreshUnread();

		expect(vm.unread).toBe(4);
	});

	it('refreshUnread keeps the last count when offline / signed out', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({ 'GET /api/v1/notifications/unread-count': { count: 4 } })
		);
		const vm = createNotifications();
		await vm.refreshUnread();

		vi.stubGlobal('fetch', failingFetch());
		await vm.refreshUnread();

		expect(vm.unread).toBe(4);
	});

	it('load fetches the inbox and derives the unread count', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/notifications': [
					NOTIFICATION('n-1'),
					NOTIFICATION('n-2', true),
					NOTIFICATION('n-3')
				]
			})
		);
		const vm = createNotifications();

		await vm.load();

		expect(vm.items.map((n) => n.id)).toEqual(['n-1', 'n-2', 'n-3']);
		expect(vm.unread).toBe(2);
		expect(vm.loading).toBe(false);
	});

	it('load exposes a loading flag while the request is in flight', async () => {
		let resolve!: (v: unknown) => void;
		vi.stubGlobal(
			'fetch',
			vi.fn(
				() =>
					new Promise((r) => {
						resolve = r;
					})
			) as unknown as typeof fetch
		);
		const vm = createNotifications();

		const pending = vm.load();
		expect(vm.loading).toBe(true);

		resolve({ ok: true, status: 200, json: async () => [NOTIFICATION('n-1')] });
		await pending;

		expect(vm.loading).toBe(false);
		expect(vm.items).toHaveLength(1);
	});

	it('a failed load keeps the previous items and clears loading', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({ 'GET /api/v1/notifications': [NOTIFICATION('n-1')] })
		);
		const vm = createNotifications();
		await vm.load();

		vi.stubGlobal('fetch', failingFetch());
		await vm.load();

		expect(vm.items.map((n) => n.id)).toEqual(['n-1']);
		expect(vm.unread).toBe(1);
		expect(vm.loading).toBe(false);
	});

	it('markRead marks the item, decrements unread and POSTs', async () => {
		const fetchMock = routedFetch({
			'GET /api/v1/notifications': [NOTIFICATION('n-1'), NOTIFICATION('n-2')],
			'POST /api/v1/notifications/n-1/read': null
		});
		vi.stubGlobal('fetch', fetchMock);
		const vm = createNotifications();
		await vm.load();

		await vm.markRead('n-1');

		expect(vm.items.find((n) => n.id === 'n-1')?.read).toBe(true);
		expect(vm.unread).toBe(1);
		expect(fetchMock).toHaveBeenCalledWith(
			'/api/v1/notifications/n-1/read',
			expect.objectContaining({ method: 'POST' })
		);
	});

	it('markRead of an already-read item does not decrement unread', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/notifications': [NOTIFICATION('n-1', true), NOTIFICATION('n-2')],
				'POST /api/v1/notifications/n-1/read': null
			})
		);
		const vm = createNotifications();
		await vm.load();

		await vm.markRead('n-1');

		expect(vm.unread).toBe(1);
	});

	it('markRead of an unknown id still POSTs without touching state', async () => {
		const fetchMock = routedFetch({
			'GET /api/v1/notifications': [NOTIFICATION('n-1')],
			'POST /api/v1/notifications/ghost/read': null
		});
		vi.stubGlobal('fetch', fetchMock);
		const vm = createNotifications();
		await vm.load();

		await vm.markRead('ghost');

		expect(vm.unread).toBe(1);
		expect(fetchMock).toHaveBeenCalledWith(
			'/api/v1/notifications/ghost/read',
			expect.objectContaining({ method: 'POST' })
		);
	});

	it('markRead never drives unread below zero', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/notifications': [NOTIFICATION('n-1')],
				'GET /api/v1/notifications/unread-count': { count: 0 },
				'POST /api/v1/notifications/n-1/read': null
			})
		);
		const vm = createNotifications();
		await vm.load();
		// The poller reports 0 (e.g. read elsewhere) while n-1 is still unread locally.
		await vm.refreshUnread();

		await vm.markRead('n-1');

		expect(vm.unread).toBe(0);
	});

	it('markRead keeps the optimistic state when the POST fails', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({ 'GET /api/v1/notifications': [NOTIFICATION('n-1')] })
		);
		const vm = createNotifications();
		await vm.load();

		vi.stubGlobal('fetch', failingFetch());
		await expect(vm.markRead('n-1')).resolves.toBeUndefined();

		expect(vm.items[0].read).toBe(true);
		expect(vm.unread).toBe(0);
	});

	it('markAll marks every item read, zeroes unread and POSTs read-all', async () => {
		const fetchMock = routedFetch({
			'GET /api/v1/notifications': [
				NOTIFICATION('n-1'),
				NOTIFICATION('n-2', true),
				NOTIFICATION('n-3')
			],
			'POST /api/v1/notifications/read-all': null
		});
		vi.stubGlobal('fetch', fetchMock);
		const vm = createNotifications();
		await vm.load();

		await vm.markAll();

		expect(vm.items.every((n) => n.read)).toBe(true);
		expect(vm.unread).toBe(0);
		expect(fetchMock).toHaveBeenCalledWith(
			'/api/v1/notifications/read-all',
			expect.objectContaining({ method: 'POST' })
		);
	});

	it('markAll keeps the optimistic state when the POST fails', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({ 'GET /api/v1/notifications': [NOTIFICATION('n-1')] })
		);
		const vm = createNotifications();
		await vm.load();

		vi.stubGlobal('fetch', failingFetch());
		await expect(vm.markAll()).resolves.toBeUndefined();

		expect(vm.items.every((n) => n.read)).toBe(true);
		expect(vm.unread).toBe(0);
	});
});
