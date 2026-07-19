import { beforeEach, describe, expect, it, vi } from 'vitest';

import { listOrgUsers } from './orgUsers';

/** Captures every request so the client's URL/method shape is asserted. */
function capturingFetch(body: unknown = null) {
	const calls: Array<{ url: string; method: string; body: unknown }> = [];
	const fn = vi.fn(async (url: string, init?: RequestInit) => {
		calls.push({
			url,
			method: init?.method ?? 'GET',
			body: init?.body ? JSON.parse(String(init.body)) : undefined
		});
		return { ok: true, status: 200, json: async () => body };
	}) as unknown as typeof fetch;
	return { fn, calls };
}

describe('orgUsers API client', () => {
	beforeEach(() => vi.restoreAllMocks());

	it('listOrgUsers gets the directory page with defaults', async () => {
		const page = { users: [], total: 0, page: 1, page_size: 50 };
		const { fn, calls } = capturingFetch(page);
		vi.stubGlobal('fetch', fn);

		expect(await listOrgUsers()).toEqual(page);
		expect(calls).toEqual([
			{ url: '/api/v1/org/users?search=&page=1&page_size=50', method: 'GET', body: undefined }
		]);
	});

	it('listOrgUsers encodes the search and pagination params', async () => {
		const { fn, calls } = capturingFetch({ users: [], total: 0, page: 2, page_size: 10 });
		vi.stubGlobal('fetch', fn);

		await listOrgUsers('ada l', 2, 10);

		expect(calls[0].url).toBe('/api/v1/org/users?search=ada+l&page=2&page_size=10');
	});
});
