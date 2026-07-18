import { afterEach, describe, expect, it, vi } from 'vitest';

import { deleteSubscription, getVapidPublicKey, saveSubscription } from './push';

describe('push API client', () => {
	afterEach(() => vi.restoreAllMocks());

	it('getVapidPublicKey returns the server key', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async () => ({ ok: true, status: 200, json: async () => ({ key: 'pub-key' }) }))
		);
		expect(await getVapidPublicKey()).toBe('pub-key');
	});

	it('getVapidPublicKey returns empty string when push is unconfigured', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async () => ({ ok: true, status: 200, json: async () => ({ key: '' }) }))
		);
		expect(await getVapidPublicKey()).toBe('');
	});

	it('saveSubscription POSTs the browser subscription shape', async () => {
		const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => ({
			ok: true,
			status: 204,
			json: async () => ({})
		}));
		vi.stubGlobal('fetch', fetchMock);

		await saveSubscription({
			endpoint: 'https://push.example/dev1',
			keys: { p256dh: 'k', auth: 's' }
		});

		const [url, init] = fetchMock.mock.calls[0];
		expect(url).toContain('/api/v1/push/subscriptions');
		expect(init?.method).toBe('POST');
		expect(JSON.parse(String(init?.body))).toEqual({
			endpoint: 'https://push.example/dev1',
			keys: { p256dh: 'k', auth: 's' }
		});
	});

	it('deleteSubscription DELETEs with the endpoint in the body', async () => {
		const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => ({
			ok: true,
			status: 204,
			json: async () => ({})
		}));
		vi.stubGlobal('fetch', fetchMock);

		await deleteSubscription('https://push.example/dev1');

		const [url, init] = fetchMock.mock.calls[0];
		expect(url).toContain('/api/v1/push/subscriptions');
		expect(init?.method).toBe('DELETE');
		expect(JSON.parse(String(init?.body))).toEqual({ endpoint: 'https://push.example/dev1' });
	});
});
