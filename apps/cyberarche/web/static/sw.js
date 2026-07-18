/* CyberArche service worker. Two jobs:
 *   1. Web Push (notifications spec) — render push events from the backend's
 *      Web Push channel and focus/open the app when one is clicked.
 *   2. Offline app shell — precache the SPA shell and route fetches so a reload
 *      works offline, WITHOUT ever caching API/auth/WebSocket traffic.
 * Plain JS, no imports — it runs in the ServiceWorker global scope.
 *
 * The fetch routing below MIRRORS src/lib/sw-routing.ts (swRoute). That TS copy
 * is unit-tested and is the source of truth; keep the two in sync. */

const CACHE = 'cyberarche-shell-v1';
// The SPA shell. '/' is the adapter-static fallback (index.html); it is what a
// navigation falls back to offline.
const SHELL = ['/', '/manifest.webmanifest', '/icons/icon-192.png'];

// --- Offline app shell -----------------------------------------------------

self.addEventListener('install', (event) => {
	event.waitUntil(
		caches
			.open(CACHE)
			.then((cache) => cache.addAll(SHELL))
			.then(() => self.skipWaiting())
	);
});

self.addEventListener('activate', (event) => {
	event.waitUntil(
		caches
			.keys()
			.then((keys) =>
				Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key)))
			)
			.then(() => self.clients.claim())
	);
});

/** Decide how to handle a request — mirror of swRoute() in sw-routing.ts. */
function swRoute(url, request) {
	if (request.method !== 'GET') return 'bypass';
	if (url.origin !== self.location.origin) return 'bypass';
	if (url.pathname.startsWith('/api/') || url.pathname.includes('/auth')) return 'bypass';
	if ((request.headers.get('upgrade') || '').toLowerCase() === 'websocket') return 'bypass';
	if (request.mode === 'navigate') return 'navigate';
	return 'asset';
}

/** Navigation: network-first, fall back to the cached shell offline. */
async function handleNavigate(request) {
	try {
		return await fetch(request);
	} catch (e) {
		const shell = await caches.match('/');
		if (shell) return shell;
		throw e;
	}
}

/** Static asset: stale-while-revalidate. */
async function handleAsset(request) {
	const cache = await caches.open(CACHE);
	const cached = await cache.match(request);
	const network = fetch(request)
		.then((response) => {
			if (response && response.ok) cache.put(request, response.clone());
			return response;
		})
		.catch(() => undefined);
	return cached || (await network) || fetch(request);
}

self.addEventListener('fetch', (event) => {
	const { request } = event;
	const url = new URL(request.url);
	const strategy = swRoute(url, request);
	if (strategy === 'bypass') return; // let the network handle it
	if (strategy === 'navigate') {
		event.respondWith(handleNavigate(request));
		return;
	}
	event.respondWith(handleAsset(request));
});

// --- Web Push (unchanged) --------------------------------------------------

self.addEventListener('push', (event) => {
	let payload = {};
	try {
		payload = event.data ? event.data.json() : {};
	} catch (e) {
		payload = {};
	}
	const title = payload.title || 'CyberArche';
	const options = {
		body: payload.body || '',
		data: { kind: payload.kind, document_id: payload.document_id }
	};
	event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', (event) => {
	event.notification.close();
	event.waitUntil(
		self.clients
			.matchAll({ type: 'window', includeUncontrolled: true })
			.then((clients) => {
				for (const client of clients) {
					if ('focus' in client) return client.focus();
				}
				if (self.clients.openWindow) return self.clients.openWindow('/');
			})
	);
});
