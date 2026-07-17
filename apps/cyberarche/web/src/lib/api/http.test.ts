import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError, configureAuth, del, get, getBlob, patch, post, postForm, put } from './http';

type FetchMock = ReturnType<typeof vi.fn>;

function mockFetch(status: number, body: unknown) {
	return vi.fn(async () => ({
		ok: status < 400,
		status,
		json: async () => body
	})) as unknown as typeof fetch;
}

/** Last call's URL and (Headers-normalized) init, for asserting request shapes. */
function callAt(fetchMock: typeof fetch, index = 0) {
	const [url, init] = (fetchMock as unknown as FetchMock).mock.calls[index];
	return { url: url as string, init: init as RequestInit, headers: init.headers as Headers };
}

describe('http core', () => {
	beforeEach(() => {
		vi.restoreAllMocks();
		// Reset the module-level auth hooks to the signed-out defaults.
		configureAuth({ getAccessToken: () => null, tryRefresh: async () => false });
	});

	it('get returns parsed JSON and sends no Authorization header when signed out', async () => {
		const fetchMock = mockFetch(200, { hello: 'world' });
		vi.stubGlobal('fetch', fetchMock);

		expect(await get('/api/v1/thing')).toEqual({ hello: 'world' });

		const { url, init, headers } = callAt(fetchMock);
		expect(url).toBe('/api/v1/thing');
		expect(init.method).toBeUndefined(); // plain GET
		expect(headers.get('Authorization')).toBeNull();
	});

	it('attaches the bearer token from the configured auth hooks', async () => {
		configureAuth({ getAccessToken: () => 'tok-1', tryRefresh: async () => false });
		const fetchMock = mockFetch(200, {});
		vi.stubGlobal('fetch', fetchMock);

		await get('/api/v1/thing');

		expect(callAt(fetchMock).headers.get('Authorization')).toBe('Bearer tok-1');
	});

	it('post serializes the body as JSON with Content-Type', async () => {
		const fetchMock = mockFetch(200, {});
		vi.stubGlobal('fetch', fetchMock);

		await post('/api/v1/thing', { a: 1 });

		const { init, headers } = callAt(fetchMock);
		expect(init.method).toBe('POST');
		expect(headers.get('Content-Type')).toBe('application/json');
		expect(JSON.parse(String(init.body))).toEqual({ a: 1 });
	});

	it('post without a body sends no body and no Content-Type', async () => {
		const fetchMock = mockFetch(200, {});
		vi.stubGlobal('fetch', fetchMock);

		await post('/api/v1/thing');

		const { init, headers } = callAt(fetchMock);
		expect(init.body).toBeUndefined();
		expect(headers.get('Content-Type')).toBeNull();
	});

	it('postForm leaves Content-Type unset so fetch adds the multipart boundary', async () => {
		const fetchMock = mockFetch(200, {});
		vi.stubGlobal('fetch', fetchMock);
		const form = new FormData();
		form.set('file', 'x');

		await postForm('/api/v1/upload', form);

		const { init, headers } = callAt(fetchMock);
		expect(init.method).toBe('POST');
		expect(init.body).toBe(form);
		expect(headers.get('Content-Type')).toBeNull();
	});

	it('patch, put and del use their HTTP methods; patch/put stringify the body', async () => {
		const fetchMock = mockFetch(200, {});
		vi.stubGlobal('fetch', fetchMock);

		await patch('/api/v1/thing', { p: 1 });
		await put('/api/v1/thing', { q: 2 });
		await del('/api/v1/thing');

		expect(callAt(fetchMock, 0).init.method).toBe('PATCH');
		expect(JSON.parse(String(callAt(fetchMock, 0).init.body))).toEqual({ p: 1 });
		expect(callAt(fetchMock, 1).init.method).toBe('PUT');
		expect(JSON.parse(String(callAt(fetchMock, 1).init.body))).toEqual({ q: 2 });
		expect(callAt(fetchMock, 2).init.method).toBe('DELETE');
		expect(callAt(fetchMock, 2).init.body).toBeUndefined();
	});

	it('retries once with the refreshed token after a 401', async () => {
		let token = 'stale';
		const tryRefresh = vi.fn(async () => {
			token = 'fresh';
			return true;
		});
		configureAuth({ getAccessToken: () => token, tryRefresh });
		const fetchMock = vi.fn(async () => ({ ok: true, status: 200, json: async () => ({ ok: 1 }) }));
		fetchMock.mockResolvedValueOnce({ ok: false, status: 401, json: async () => ({}) } as never);
		vi.stubGlobal('fetch', fetchMock);

		expect(await get('/api/v1/thing')).toEqual({ ok: 1 });

		expect(tryRefresh).toHaveBeenCalledTimes(1);
		expect(fetchMock).toHaveBeenCalledTimes(2);
		expect(callAt(fetchMock as unknown as typeof fetch, 0).headers.get('Authorization')).toBe(
			'Bearer stale'
		);
		expect(callAt(fetchMock as unknown as typeof fetch, 1).headers.get('Authorization')).toBe(
			'Bearer fresh'
		);
	});

	it('gives up after a second 401 instead of refreshing again', async () => {
		const tryRefresh = vi.fn(async () => true);
		configureAuth({ getAccessToken: () => 'tok', tryRefresh });
		const fetchMock = mockFetch(401, { detail: 'expired' });
		vi.stubGlobal('fetch', fetchMock);

		await expect(get('/api/v1/thing')).rejects.toMatchObject({ status: 401, detail: 'expired' });

		expect(tryRefresh).toHaveBeenCalledTimes(1); // not retried on the retry
		expect(fetchMock).toHaveBeenCalledTimes(2);
	});

	it('throws without retrying when the refresh fails', async () => {
		const tryRefresh = vi.fn(async () => false);
		configureAuth({ getAccessToken: () => 'tok', tryRefresh });
		const fetchMock = mockFetch(401, { detail: 'nope' });
		vi.stubGlobal('fetch', fetchMock);

		await expect(get('/api/v1/thing')).rejects.toThrowError(ApiError);

		expect(fetchMock).toHaveBeenCalledTimes(1);
	});

	it('surfaces the error body detail in the ApiError', async () => {
		vi.stubGlobal('fetch', mockFetch(403, { detail: 'forbidden' }));

		const error = await get('/api/v1/thing').catch((e: unknown) => e);

		expect(error).toBeInstanceOf(ApiError);
		expect(error).toMatchObject({ status: 403, detail: 'forbidden' });
		expect((error as ApiError).message).toBe('403: forbidden');
	});

	it('falls back to statusText when the error body is not JSON', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async () => ({
				ok: false,
				status: 500,
				statusText: 'Internal Server Error',
				json: async () => {
					throw new SyntaxError('not json');
				}
			})) as unknown as typeof fetch
		);

		await expect(get('/api/v1/thing')).rejects.toMatchObject({
			status: 500,
			detail: 'Internal Server Error'
		});
	});

	it('falls back to statusText when the error body has no detail', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async () => ({
				ok: false,
				status: 400,
				statusText: 'Bad Request',
				json: async () => ({})
			})) as unknown as typeof fetch
		);

		await expect(get('/api/v1/thing')).rejects.toMatchObject({
			status: 400,
			detail: 'Bad Request'
		});
	});

	it('resolves undefined for 204 No Content without reading a body', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async () => ({
				ok: true,
				status: 204,
				json: async () => {
					throw new SyntaxError('no body');
				}
			})) as unknown as typeof fetch
		);

		expect(await del('/api/v1/thing')).toBeUndefined();
	});

	describe('getBlob', () => {
		it('returns the blob with bearer auth', async () => {
			configureAuth({ getAccessToken: () => 'tok-1', tryRefresh: async () => false });
			const blob = new Blob(['png-bytes']);
			const fetchMock = vi.fn(async () => ({ ok: true, status: 200, blob: async () => blob }));
			vi.stubGlobal('fetch', fetchMock);

			expect(await getBlob('/api/v1/files/1')).toBe(blob);

			const { url, headers } = callAt(fetchMock as unknown as typeof fetch);
			expect(url).toBe('/api/v1/files/1');
			expect(headers.get('Authorization')).toBe('Bearer tok-1');
		});

		it('resends once after a 401 when refresh succeeds', async () => {
			let token = 'stale';
			configureAuth({
				getAccessToken: () => token,
				tryRefresh: async () => {
					token = 'fresh';
					return true;
				}
			});
			const blob = new Blob(['img']);
			const fetchMock = vi.fn(async () => ({ ok: true, status: 200, blob: async () => blob }));
			fetchMock.mockResolvedValueOnce({ ok: false, status: 401 } as never);
			vi.stubGlobal('fetch', fetchMock);

			expect(await getBlob('/api/v1/files/1')).toBe(blob);

			expect(fetchMock).toHaveBeenCalledTimes(2);
			expect(callAt(fetchMock as unknown as typeof fetch, 1).headers.get('Authorization')).toBe(
				'Bearer fresh'
			);
		});

		it('throws ApiError when the refresh fails on a 401', async () => {
			const fetchMock = vi.fn(async () => ({ ok: false, status: 401, statusText: 'Unauthorized' }));
			vi.stubGlobal('fetch', fetchMock);

			await expect(getBlob('/api/v1/files/1')).rejects.toMatchObject({
				status: 401,
				detail: 'Unauthorized'
			});
			expect(fetchMock).toHaveBeenCalledTimes(1);
		});

		it('throws ApiError with the statusText on other failures, signed out', async () => {
			const fetchMock = vi.fn(async () => ({ ok: false, status: 404, statusText: 'Not Found' }));
			vi.stubGlobal('fetch', fetchMock);

			await expect(getBlob('/api/v1/files/missing')).rejects.toThrowError(ApiError);
			await expect(getBlob('/api/v1/files/missing')).rejects.toMatchObject({
				status: 404,
				detail: 'Not Found'
			});
			// Signed out: no Authorization header is sent.
			expect(callAt(fetchMock as unknown as typeof fetch).headers.get('Authorization')).toBeNull();
		});
	});
});
