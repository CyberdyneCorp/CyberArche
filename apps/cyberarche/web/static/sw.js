/* Web Push service worker (notifications spec). Renders push events sent by the
 * backend's Web Push channel and focuses/opens the app when one is clicked.
 * Plain JS, no imports — it runs in the ServiceWorker global scope. */

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
