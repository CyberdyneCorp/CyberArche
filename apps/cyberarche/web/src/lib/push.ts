/** Browser Web Push client (notifications spec): register the service worker,
 * subscribe/unsubscribe the browser, and forward the subscription to the API.
 * Every helper is feature-guarded — in a non-supporting environment (SSR, or a
 * browser without service workers / PushManager) it is a no-op returning false.
 * The Web APIs live here; the ViewModel orchestrates them (MVVM). */
import {
	deleteSubscription,
	getVapidPublicKey as apiGetVapidPublicKey,
	saveSubscription,
	type BrowserSubscription
} from '$lib/api/push';

/** Whether this environment can do Web Push at all. */
function pushSupported(): boolean {
	return (
		typeof window !== 'undefined' &&
		'serviceWorker' in navigator &&
		'PushManager' in window
	);
}

/** Decode a base64url VAPID key into the Uint8Array the PushManager expects. */
function urlBase64ToUint8Array(base64String: string): Uint8Array {
	const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
	const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
	const raw = atob(base64);
	const output = new Uint8Array(raw.length);
	for (let i = 0; i < raw.length; i++) output[i] = raw.charCodeAt(i);
	return output;
}

/** The server's VAPID public key, or '' when push is unavailable/unconfigured. */
export async function getVapidPublicKey(): Promise<string> {
	if (!pushSupported()) return '';
	return apiGetVapidPublicKey();
}

/** Subscribe this browser to push and persist the subscription server-side.
 * Returns false when unsupported, unconfigured, or the user denies permission. */
export async function enablePush(vapidPublicKey: string): Promise<boolean> {
	if (!pushSupported() || !vapidPublicKey) return false;
	const registration = await navigator.serviceWorker.register('/sw.js');
	const permission = await Notification.requestPermission();
	if (permission !== 'granted') return false;
	const subscription = await registration.pushManager.subscribe({
		userVisibleOnly: true,
		applicationServerKey: urlBase64ToUint8Array(vapidPublicKey) as BufferSource
	});
	await saveSubscription(subscription.toJSON() as BrowserSubscription);
	return true;
}

/** Remove this browser's push subscription (best-effort). */
export async function disablePush(): Promise<boolean> {
	if (!pushSupported()) return false;
	const registration = await navigator.serviceWorker.getRegistration('/sw.js');
	const subscription = await registration?.pushManager.getSubscription();
	if (!subscription) return false;
	await deleteSubscription(subscription.endpoint);
	await subscription.unsubscribe();
	return true;
}
