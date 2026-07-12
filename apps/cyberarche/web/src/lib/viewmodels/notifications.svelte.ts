/** Notifications view-model (mentions-and-notifications): a module singleton
 * holding the unread count (polled) and the loaded inbox. */
import {
	listNotifications,
	markAllNotificationsRead,
	markNotificationRead,
	notificationsUnreadCount,
	type AppNotification
} from '$lib/api/notifications';

export function createNotifications() {
	let items = $state<AppNotification[]>([]);
	let unread = $state(0);
	let loading = $state(false);

	async function refreshUnread(): Promise<void> {
		try {
			unread = (await notificationsUnreadCount()).count;
		} catch {
			/* offline / signed out — leave the last count */
		}
	}

	return {
		get items() {
			return items;
		},
		get unread() {
			return unread;
		},
		get loading() {
			return loading;
		},
		refreshUnread,
		async load(): Promise<void> {
			loading = true;
			try {
				items = await listNotifications();
				unread = items.filter((n) => !n.read).length;
			} catch {
				/* ignore */
			} finally {
				loading = false;
			}
		},
		async markRead(id: string): Promise<void> {
			const n = items.find((x) => x.id === id);
			if (n && !n.read) {
				n.read = true;
				unread = Math.max(0, unread - 1);
			}
			try {
				await markNotificationRead(id);
			} catch {
				/* best effort */
			}
		},
		async markAll(): Promise<void> {
			for (const n of items) n.read = true;
			unread = 0;
			try {
				await markAllNotificationsRead();
			} catch {
				/* best effort */
			}
		}
	};
}

export const notifications = createNotifications();
