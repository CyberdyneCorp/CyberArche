import { beforeEach, describe, expect, it, vi } from 'vitest';

import { createApiKey, listApiKeys, revokeApiKey } from './apiKeys';

const KEY = {
	id: 'key-1',
	name: 'CLI',
	prefix: 'ca_abc',
	created_at: '2026-01-01T00:00:00Z',
	expires_at: null,
	revoked: false,
	last_used_at: null
};

function mockFetch(status: number, body: unknown) {
	return vi.fn(async () => ({
		ok: status < 400,
		status,
		json: async () => body
	})) as unknown as typeof fetch;
}

describe('apiKeys api client', () => {
	beforeEach(() => vi.restoreAllMocks());

	it('createApiKey POSTs the name and returns the created key with its secret', async () => {
		const fetchMock = mockFetch(200, { ...KEY, secret: 'ca_abc.s3cr3t' });
		vi.stubGlobal('fetch', fetchMock);

		const created = await createApiKey('CLI');

		expect(created.secret).toBe('ca_abc.s3cr3t');
		const [url, init] = (fetchMock as ReturnType<typeof vi.fn>).mock.calls[0];
		expect(url).toBe('/api/v1/api-keys');
		expect(init.method).toBe('POST');
		expect(JSON.parse(init.body)).toEqual({ name: 'CLI' });
	});

	it('listApiKeys GETs the collection', async () => {
		const fetchMock = mockFetch(200, [KEY]);
		vi.stubGlobal('fetch', fetchMock);

		const keys = await listApiKeys();

		expect(keys).toEqual([KEY]);
		const [url, init] = (fetchMock as ReturnType<typeof vi.fn>).mock.calls[0];
		expect(url).toBe('/api/v1/api-keys');
		expect(init.method).toBeUndefined();
	});

	it('revokeApiKey DELETEs the key by id and returns the revoked record', async () => {
		const fetchMock = mockFetch(200, { ...KEY, revoked: true });
		vi.stubGlobal('fetch', fetchMock);

		const revoked = await revokeApiKey('key-1');

		expect(revoked.revoked).toBe(true);
		const [url, init] = (fetchMock as ReturnType<typeof vi.fn>).mock.calls[0];
		expect(url).toBe('/api/v1/api-keys/key-1');
		expect(init.method).toBe('DELETE');
	});

	it('propagates API errors from the http layer', async () => {
		vi.stubGlobal('fetch', mockFetch(403, { detail: 'forbidden' }));

		await expect(createApiKey('CLI')).rejects.toThrow('403: forbidden');
	});
});
