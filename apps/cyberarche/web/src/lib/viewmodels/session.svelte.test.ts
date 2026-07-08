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
});
