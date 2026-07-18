import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { createNotificationPrefs } from './notificationPrefs.svelte';

const enablePush = vi.fn();
const disablePush = vi.fn();
const getVapidPublicKey = vi.fn();

vi.mock('$lib/push', () => ({
	enablePush: (...args: unknown[]) => enablePush(...args),
	disablePush: (...args: unknown[]) => disablePush(...args),
	getVapidPublicKey: (...args: unknown[]) => getVapidPublicKey(...args)
}));

const PREFS = (overrides: Record<string, boolean> = {}) => ({
	email_enabled: false,
	push_enabled: false,
	mentions_enabled: true,
	agent_results_enabled: true,
	...overrides
});

/** Records PUT bodies so we can assert what the VM persisted (and rolled back). */
function routedFetch() {
	const puts: unknown[] = [];
	const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
		if (init?.method === 'PUT') {
			const body = JSON.parse(String(init.body));
			puts.push(body);
			return { ok: true, status: 200, json: async () => body };
		}
		return { ok: true, status: 200, json: async () => PREFS() };
	});
	return { fetchMock: fetchMock as unknown as typeof fetch, puts };
}

describe('notification prefs push toggle', () => {
	beforeEach(() => {
		enablePush.mockReset();
		disablePush.mockReset();
		getVapidPublicKey.mockReset();
	});
	afterEach(() => vi.restoreAllMocks());

	it('enabling push subscribes the browser via getVapidPublicKey + enablePush', async () => {
		getVapidPublicKey.mockResolvedValue('pub-key');
		enablePush.mockResolvedValue(true);
		const { fetchMock } = routedFetch();
		vi.stubGlobal('fetch', fetchMock);
		const vm = createNotificationPrefs();
		await vm.load();

		await vm.toggle('push_enabled');

		expect(vm.prefs.push_enabled).toBe(true);
		expect(getVapidPublicKey).toHaveBeenCalledOnce();
		expect(enablePush).toHaveBeenCalledWith('pub-key');
		expect(vm.error).toBeNull();
	});

	it('rolls back the flip when the VAPID key is empty (push unavailable)', async () => {
		getVapidPublicKey.mockResolvedValue('');
		enablePush.mockResolvedValue(false); // empty key => enablePush refuses
		const { fetchMock, puts } = routedFetch();
		vi.stubGlobal('fetch', fetchMock);
		const vm = createNotificationPrefs();
		await vm.load();

		await vm.toggle('push_enabled');

		// The optimistic flip is rolled back and an error is surfaced.
		expect(vm.prefs.push_enabled).toBe(false);
		expect(vm.error).toMatch(/unavailable|denied/i);
		expect(vm.busy).toBe(false);
		// The PUT that saved push_enabled:true is followed by a re-PUT that
		// restores push_enabled:false, so client and server agree.
		expect(puts.at(-1)).toEqual(PREFS({ push_enabled: false }));
	});

	it('disabling push best-effort unsubscribes the browser', async () => {
		disablePush.mockResolvedValue(true);
		const { fetchMock } = routedFetch();
		vi.stubGlobal('fetch', fetchMock);
		const vm = createNotificationPrefs();
		await vm.load();
		// Start from push on (no browser side-effect asserted on this setup PUT).
		enablePush.mockResolvedValue(true);
		getVapidPublicKey.mockResolvedValue('pub-key');
		await vm.toggle('push_enabled');

		await vm.toggle('push_enabled'); // now turning it OFF

		expect(vm.prefs.push_enabled).toBe(false);
		expect(disablePush).toHaveBeenCalledOnce();
		expect(vm.error).toBeNull();
	});
});
