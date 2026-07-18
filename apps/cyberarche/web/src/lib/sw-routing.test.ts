import { describe, expect, it } from 'vitest';

import { swRoute, type RoutableRequest } from './sw-routing';

const ORIGIN = 'https://app.cyberarche.test';

function req(overrides: Partial<RoutableRequest> = {}): RoutableRequest {
	return {
		method: 'GET',
		mode: 'no-cors',
		headers: { get: () => null },
		...overrides
	};
}

describe('swRoute', () => {
	it('bypasses API traffic', () => {
		expect(swRoute(new URL(`${ORIGIN}/api/v1/documents/1`), req(), ORIGIN)).toBe('bypass');
	});

	it('bypasses auth traffic', () => {
		expect(swRoute(new URL(`${ORIGIN}/api/v1/auth/refresh`), req(), ORIGIN)).toBe('bypass');
	});

	it('bypasses cross-origin requests (the VITE_API_URL backend)', () => {
		expect(swRoute(new URL('https://api.other.test/thing'), req(), ORIGIN)).toBe('bypass');
	});

	it('bypasses non-GET requests', () => {
		expect(
			swRoute(new URL(`${ORIGIN}/icons/icon-192.png`), req({ method: 'POST' }), ORIGIN)
		).toBe('bypass');
	});

	it('bypasses WebSocket upgrades', () => {
		const headers = { get: (n: string) => (n === 'upgrade' ? 'websocket' : null) };
		expect(swRoute(new URL(`${ORIGIN}/relay`), req({ headers }), ORIGIN)).toBe('bypass');
	});

	it('routes navigations to the shell-fallback strategy', () => {
		expect(swRoute(new URL(`${ORIGIN}/w/abc`), req({ mode: 'navigate' }), ORIGIN)).toBe(
			'navigate'
		);
	});

	it('routes _app build assets to the asset strategy', () => {
		expect(
			swRoute(new URL(`${ORIGIN}/_app/immutable/chunks/index.abc123.js`), req(), ORIGIN)
		).toBe('asset');
	});

	it('routes same-origin static images to the asset strategy', () => {
		expect(swRoute(new URL(`${ORIGIN}/icons/favicon.png`), req(), ORIGIN)).toBe('asset');
	});
});
