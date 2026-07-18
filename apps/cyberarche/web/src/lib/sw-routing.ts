/** Service-worker fetch routing rules for the offline app shell.
 *
 * This module is the single source of truth for how the service worker decides
 * what to do with a request. `static/sw.js` MIRRORS this logic (it must stay in
 * sync — see the comment block there); it cannot import this module because it
 * runs in the plain ServiceWorker global scope with no bundler. This TS copy
 * documents the rules and is what the unit tests exercise.
 *
 * Strategies:
 *  - 'bypass'  → never touch the cache; go straight to the network. Used for
 *                API/auth/WebSocket traffic, cross-origin requests, and any
 *                non-GET request.
 *  - 'navigate'→ network-first, falling back to the cached shell ('/') offline.
 *  - 'asset'   → same-origin static asset: stale-while-revalidate.
 */
export type SwStrategy = 'bypass' | 'navigate' | 'asset';

/** The minimal shape of a request the router needs (a real `Request` satisfies
 * it; tests can pass a plain object). */
export interface RoutableRequest {
	method: string;
	mode?: string;
	headers?: { get(name: string): string | null };
}

/** Decide how the service worker should handle a request.
 *
 * @param url     the parsed request URL
 * @param request the request (method/mode/headers)
 * @param origin  the service worker's own origin (defaults to the URL's origin
 *                only matters for the cross-origin check; pass `self.location.origin`
 *                in the SW).
 */
export function swRoute(
	url: URL,
	request: RoutableRequest,
	origin: string
): SwStrategy {
	// Only GET requests are ever cacheable; everything else bypasses.
	if (request.method !== 'GET') return 'bypass';

	// Cross-origin (e.g. the VITE_API_URL backend host, CDNs): never cache.
	if (url.origin !== origin) return 'bypass';

	// API and auth traffic must never be cached or served stale.
	if (url.pathname.startsWith('/api/') || url.pathname.includes('/auth')) {
		return 'bypass';
	}

	// WebSocket upgrades (the CRDT relay) — belt-and-suspenders: these don't
	// normally reach the fetch handler, and the /api/ path already covers the
	// relay, but treat an explicit Upgrade: websocket as a bypass too.
	if (request.headers?.get('upgrade')?.toLowerCase() === 'websocket') {
		return 'bypass';
	}

	// Full-page navigations: network-first with an offline shell fallback.
	if (request.mode === 'navigate') return 'navigate';

	// Everything else same-origin (scripts, styles, images, fonts, _app/ build
	// assets): stale-while-revalidate.
	return 'asset';
}
