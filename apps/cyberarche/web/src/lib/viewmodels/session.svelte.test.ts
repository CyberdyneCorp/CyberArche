import { beforeEach, describe, expect, it, vi } from 'vitest';

import { createSession } from './session.svelte';

const TOKENS = {
	access_token: 'access-1',
	refresh_token: 'refresh-1',
	token_type: 'bearer'
};

function mockFetch(status: number, body: unknown) {
	return vi.fn(async () => ({
		ok: status < 400,
		status,
		json: async () => body
	})) as unknown as typeof fetch;
}

describe('session ViewModel', () => {
	beforeEach(() => localStorage.clear());

	it('login stores tokens and authenticates', async () => {
		vi.stubGlobal('fetch', mockFetch(200, TOKENS));
		const session = createSession();

		expect(await session.login('u@t.io', 'pw')).toBe(true);

		expect(session.isAuthenticated).toBe(true);
		expect(session.getAccessToken()).toBe('access-1');
		expect(localStorage.getItem('cyberarche.session')).toContain('refresh-1');
	});

	it('failed login surfaces an error and stays signed out', async () => {
		vi.stubGlobal('fetch', mockFetch(401, { detail: 'nope' }));
		const session = createSession();

		expect(await session.login('u@t.io', 'bad')).toBe(false);

		expect(session.isAuthenticated).toBe(false);
		expect(session.error).toMatch(/failed/i);
	});

	it('restore rehydrates a persisted session and logout clears it', async () => {
		localStorage.setItem(
			'cyberarche.session',
			JSON.stringify({ access: 'a', refresh: 'r' })
		);
		const session = createSession();

		expect(session.restore()).toBe(true);
		expect(session.isAuthenticated).toBe(true);

		session.logout();
		expect(session.isAuthenticated).toBe(false);
		expect(localStorage.getItem('cyberarche.session')).toBeNull();
	});

	it('tryRefresh rotates tokens', async () => {
		vi.stubGlobal(
			'fetch',
			mockFetch(200, { ...TOKENS, access_token: 'access-2', refresh_token: 'refresh-2' })
		);
		localStorage.setItem(
			'cyberarche.session',
			JSON.stringify({ access: 'a', refresh: 'r' })
		);
		const session = createSession();
		session.restore();

		expect(await session.tryRefresh()).toBe(true);
		expect(session.getAccessToken()).toBe('access-2');
	});

	it('restore returns false when nothing or garbage is stored', () => {
		const session = createSession();
		expect(session.restore()).toBe(false);

		localStorage.setItem('cyberarche.session', 'not-json');
		expect(session.restore()).toBe(false);
		expect(session.isAuthenticated).toBe(false);
	});

	it('userId decodes the JWT subject and tolerates malformed tokens', () => {
		const jwt = (payload: Record<string, unknown>) =>
			`header.${btoa(JSON.stringify(payload))}.sig`;
		const session = createSession();
		expect(session.userId).toBeNull(); // signed out

		localStorage.setItem(
			'cyberarche.session',
			JSON.stringify({ access: jwt({ sub: 'user-7' }), refresh: 'r' })
		);
		session.restore();
		expect(session.userId).toBe('user-7');

		localStorage.setItem(
			'cyberarche.session',
			JSON.stringify({ access: jwt({}), refresh: 'r' })
		);
		session.restore();
		expect(session.userId).toBeNull(); // no sub claim

		localStorage.setItem(
			'cyberarche.session',
			JSON.stringify({ access: 'garbage', refresh: 'r' })
		);
		session.restore();
		expect(session.userId).toBeNull(); // undecodable token
	});

	it('tryRefresh returns false without a refresh token', async () => {
		const session = createSession();
		expect(await session.tryRefresh()).toBe(false);
	});

	it('a rejected refresh logs the session out', async () => {
		// 403 (revoked), not 401: a 401 would re-enter the HTTP core's
		// refresh-retry and recurse (see http.ts request()).
		vi.stubGlobal('fetch', mockFetch(403, { detail: 'revoked' }));
		localStorage.setItem(
			'cyberarche.session',
			JSON.stringify({ access: 'a', refresh: 'r' })
		);
		const session = createSession();
		session.restore();

		expect(await session.tryRefresh()).toBe(false);
		expect(session.isAuthenticated).toBe(false);
		expect(localStorage.getItem('cyberarche.session')).toBeNull();
	});

	it('works without localStorage (SSR-safe guards)', async () => {
		vi.stubGlobal('fetch', mockFetch(200, TOKENS));
		vi.stubGlobal('localStorage', undefined);
		try {
			const session = createSession();
			expect(session.restore()).toBe(false);
			expect(await session.login('u@t.io', 'pw')).toBe(true); // persist is a no-op
			expect(session.isAuthenticated).toBe(true);
			expect(session.busy).toBe(false);
		} finally {
			vi.unstubAllGlobals();
		}
	});
});
