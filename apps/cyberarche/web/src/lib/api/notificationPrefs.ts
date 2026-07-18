/** Notification preferences (notifications spec): the caller's own delivery
 * toggles. In-app is always on and not represented here. */
import { get, put } from './http';

export interface NotificationPrefs {
	email_enabled: boolean;
	push_enabled: boolean;
	mentions_enabled: boolean;
	agent_results_enabled: boolean;
}

export const getPrefs = () => get<NotificationPrefs>('/api/v1/notification-preferences');

export const updatePrefs = (prefs: NotificationPrefs) =>
	put<NotificationPrefs>('/api/v1/notification-preferences', prefs);
