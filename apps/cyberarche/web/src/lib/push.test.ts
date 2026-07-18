import { describe, expect, it, vi } from 'vitest';

import { disablePush, enablePush, getVapidPublicKey } from './push';

// jsdom has neither `serviceWorker` on navigator nor `PushManager` on window,
// so this exercises the "non-supporting environment" guard: every helper is a
// no-op that returns false / '' without touching the network or Web APIs.
describe('push client feature guards', () => {
	it('getVapidPublicKey returns "" without calling the API when unsupported', async () => {
		const fetchMock = vi.fn();
		vi.stubGlobal('fetch', fetchMock);
		expect(await getVapidPublicKey()).toBe('');
		expect(fetchMock).not.toHaveBeenCalled();
		vi.unstubAllGlobals();
	});

	it('enablePush returns false when the browser does not support push', async () => {
		expect(await enablePush('any-key')).toBe(false);
	});

	it('disablePush returns false when the browser does not support push', async () => {
		expect(await disablePush()).toBe(false);
	});
});
