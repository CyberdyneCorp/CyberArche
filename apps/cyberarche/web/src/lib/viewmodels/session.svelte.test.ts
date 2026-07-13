import { beforeEach, describe, expect, it, vi } from 'vitest';

import { createSession } from './session.svelte';

const ACCESS = { access_token: 'access-1', token_type: 'bearer' };

/** Mock fetch. The refresh token lives in an HttpOnly cookie the browser
 * manages, so it never appears in these bodies (F-004). */
function mockFetch(status: number, body: unknown) {
	return vi.fn(async () => ({
		ok: status < 400,
		status,
		json: async () => body
	})) as unknown as typeof fetch;
}

const jwt = (payload: Record<string, unknown>) =>
	`header.${btoa(JSON.stringify(payload))}.sig`;

describe('session ViewModel', () => {
	beforeEach(() => vi.restoreAllMocks());

	it('login stores only the access token in memory (never localStorage)', async () => {
		const fetchMock = mockFetch(200, ACCESS);
		vi.stubGlobal('fetch', fetchMock);
		const session = createSession();

		expect(await session.login('u@t.io', 'pw')).toBe(true);

		expect(session.isAuthenticated).toBe(true);
		expect(session.getAccessToken()).toBe('access-1');
		// F-004: nothing sensitive is persisted to JS-readable storage.
		expect(localStorage.getItem('cyberarche.session')).toBeNull();
		// The login request opts into cookies so the Set-Cookie is stored.
		const init = fetchMock.mock.calls[0][1] as RequestInit;
		expect(init.credentials).toBe('include');
	});

	it('failed login surfaces an error and stays signed out', async () => {
		vi.stubGlobal('fetch', mockFetch(401, { detail: 'nope' }));
		const session = createSession();

		expect(await session.login('u@t.io', 'bad')).toBe(false);

		expect(session.isAuthenticated).toBe(false);
		expect(session.error).toMatch(/failed/i);
	});

	it('init restores a session via the cookie (silent refresh) and clears restoring', async () => {
		vi.stubGlobal('fetch', mockFetch(200, { access_token: 'access-2', token_type: 'bearer' }));
		const session = createSession();
		expect(session.restoring).toBe(true);

		await session.init();

		expect(session.restoring).toBe(false);
		expect(session.isAuthenticated).toBe(true);
		expect(session.getAccessToken()).toBe('access-2');
	});

	it('init with no valid cookie ends unauthenticated but done restoring', async () => {
		vi.stubGlobal('fetch', mockFetch(401, { detail: 'no session' }));
		const session = createSession();

		await session.init();

		expect(session.restoring).toBe(false);
		expect(session.isAuthenticated).toBe(false);
	});

	it('tryRefresh sends no body and includes credentials (cookie carries refresh)', async () => {
		const fetchMock = mockFetch(200, { access_token: 'access-2', token_type: 'bearer' });
		vi.stubGlobal('fetch', fetchMock);
		const session = createSession();

		expect(await session.tryRefresh()).toBe(true);
		expect(session.getAccessToken()).toBe('access-2');
		const init = fetchMock.mock.calls[0][1] as RequestInit;
		expect(init.credentials).toBe('include');
		expect(init.body).toBeUndefined();
	});

	it('a rejected refresh clears the session', async () => {
		vi.stubGlobal('fetch', mockFetch(401, { detail: 'expired' }));
		const session = createSession();

		expect(await session.tryRefresh()).toBe(false);
		expect(session.isAuthenticated).toBe(false);
	});

	it('logout calls the server to clear the cookie and drops the access token', async () => {
		const fetchMock = mockFetch(204, {});
		vi.stubGlobal('fetch', fetchMock);
		const session = createSession();
		await session.login('u@t.io', 'pw'); // one call
		fetchMock.mockClear();

		await session.logout();

		expect(session.isAuthenticated).toBe(false);
		const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
		expect(url).toContain('/api/v1/auth/session/logout');
		expect(init.credentials).toBe('include');
	});

	it('logout clears the session even if the network call fails', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async () => {
				throw new Error('offline');
			}) as unknown as typeof fetch
		);
		const session = createSession();
		await session.tryRefresh().catch(() => {});

		await session.logout();
		expect(session.isAuthenticated).toBe(false);
	});

	it('userId decodes the JWT subject and tolerates malformed tokens', async () => {
		let session = createSession();
		expect(session.userId).toBeNull(); // signed out

		vi.stubGlobal('fetch', mockFetch(200, { access_token: jwt({ sub: 'user-7' }), token_type: 'bearer' }));
		session = createSession();
		await session.login('u@t.io', 'pw');
		expect(session.userId).toBe('user-7');

		vi.stubGlobal('fetch', mockFetch(200, { access_token: jwt({}), token_type: 'bearer' }));
		session = createSession();
		await session.login('u@t.io', 'pw');
		expect(session.userId).toBeNull(); // no sub claim

		vi.stubGlobal('fetch', mockFetch(200, { access_token: 'garbage', token_type: 'bearer' }));
		session = createSession();
		await session.login('u@t.io', 'pw');
		expect(session.userId).toBeNull(); // undecodable token
	});
});
