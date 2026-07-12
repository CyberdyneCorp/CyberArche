/** Notifications inbox (mentions-and-notifications). */
import { get, post } from './http';

export interface AppNotification {
	id: string;
	kind: string;
	actor_id: string;
	document_id: string | null;
	comment_id: string | null;
	snippet: string;
	read: boolean;
	created_at: string;
}

export const listNotifications = () => get<AppNotification[]>('/api/v1/notifications');

export const notificationsUnreadCount = () =>
	get<{ count: number }>('/api/v1/notifications/unread-count');

export const markNotificationRead = (id: string) =>
	post<void>(`/api/v1/notifications/${id}/read`, {});

export const markAllNotificationsRead = () =>
	post<void>('/api/v1/notifications/read-all', {});
