import { beforeEach, describe, expect, it, vi } from 'vitest';

import { createNotificationPrefs } from './notificationPrefs.svelte';

const PREFS = (overrides: Record<string, boolean> = {}) => ({
	email_enabled: false,
	push_enabled: false,
	mentions_enabled: true,
	agent_results_enabled: true,
	...overrides
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

describe('notification preferences ViewModel', () => {
	beforeEach(() => vi.restoreAllMocks());

	it('load populates the prefs from the API', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/notification-preferences': PREFS({ email_enabled: true })
			})
		);
		const vm = createNotificationPrefs();
		await vm.load();

		expect(vm.prefs.email_enabled).toBe(true);
		expect(vm.prefs.mentions_enabled).toBe(true);
		expect(vm.error).toBeNull();
	});

	it('load surfaces an ApiError with its status', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async () => ({
				ok: false,
				status: 403,
				json: async () => ({ detail: 'nope' })
			})) as unknown as typeof fetch
		);
		const vm = createNotificationPrefs();
		await vm.load();

		expect(vm.error).toMatch(/403/);
	});

	it('toggle optimistically flips and PUTs the whole set', async () => {
		const fetchMock = routedFetch({
			'GET /api/v1/notification-preferences': PREFS(),
			'PUT /api/v1/notification-preferences': PREFS({ email_enabled: true })
		});
		vi.stubGlobal('fetch', fetchMock);
		const vm = createNotificationPrefs();
		await vm.load();

		await vm.toggle('email_enabled');

		expect(vm.prefs.email_enabled).toBe(true);
		const putCall = (fetchMock as unknown as ReturnType<typeof vi.fn>).mock.calls.find(
			([, init]) => init?.method === 'PUT'
		);
		expect(JSON.parse(String(putCall?.[1]?.body))).toEqual(PREFS({ email_enabled: true }));
		expect(vm.busy).toBe(false);
		expect(vm.error).toBeNull();
	});

	it('toggle rolls back the optimistic flip when the PUT fails', async () => {
		let failNext = false;
		vi.stubGlobal(
			'fetch',
			vi.fn(async (_url: string, init?: RequestInit) => {
				if (init?.method === 'PUT') {
					return { ok: false, status: 500, json: async () => ({ detail: 'boom' }) };
				}
				failNext = true;
				return { ok: true, status: 200, json: async () => PREFS() };
			}) as unknown as typeof fetch
		);
		const vm = createNotificationPrefs();
		await vm.load();
		expect(failNext).toBe(true);

		await vm.toggle('mentions_enabled');

		// Rolled back to the loaded value.
		expect(vm.prefs.mentions_enabled).toBe(true);
		expect(vm.error).toMatch(/500/);
		expect(vm.busy).toBe(false);
	});
});
