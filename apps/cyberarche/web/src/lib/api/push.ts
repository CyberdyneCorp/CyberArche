/** Web Push API (notifications spec): the VAPID public key and the caller's
 * browser push subscription. The browser-side Web APIs live in $lib/push. */
import { get, post, request } from './http';

export interface BrowserSubscription {
	endpoint: string;
	keys: { p256dh: string; auth: string };
}

/** The server's VAPID public key, or '' when push is not configured. */
export const getVapidPublicKey = async (): Promise<string> => {
	const { key } = await get<{ key: string }>('/api/v1/push/vapid-public-key');
	return key;
};

export const saveSubscription = (subscription: BrowserSubscription) =>
	post<void>('/api/v1/push/subscriptions', subscription);

export const deleteSubscription = (endpoint: string) =>
	request<void>('/api/v1/push/subscriptions', {
		method: 'DELETE',
		body: JSON.stringify({ endpoint })
	});
