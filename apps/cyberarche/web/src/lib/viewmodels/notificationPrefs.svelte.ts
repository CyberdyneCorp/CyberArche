/** Notification preferences ViewModel (notifications spec): load the caller's
 * delivery toggles and flip one optimistically (PUT the whole set, roll back on
 * failure). In-app is always on and not represented here. */
import { getPrefs, updatePrefs, type NotificationPrefs } from '$lib/api/notificationPrefs';
import { ApiError } from '$lib/api/http';

export type NotificationPrefKey = keyof NotificationPrefs;

const DEFAULTS: NotificationPrefs = {
	email_enabled: false,
	push_enabled: false,
	mentions_enabled: true,
	agent_results_enabled: true
};

export function createNotificationPrefs() {
	let prefs = $state<NotificationPrefs>({ ...DEFAULTS });
	let error = $state<string | null>(null);
	let busy = $state(false);

	function fail(e: unknown): void {
		error = e instanceof ApiError ? `${e.status}: ${e.message}` : String(e);
	}

	return {
		get prefs() {
			return prefs;
		},
		get error() {
			return error;
		},
		get busy() {
			return busy;
		},

		async load(): Promise<void> {
			try {
				prefs = await getPrefs();
				error = null;
			} catch (e) {
				fail(e);
			}
		},

		async toggle(key: NotificationPrefKey): Promise<void> {
			const previous = { ...prefs };
			prefs = { ...prefs, [key]: !prefs[key] };
			busy = true;
			error = null;
			try {
				prefs = await updatePrefs(prefs);
			} catch (e) {
				prefs = previous; // roll back the optimistic flip
				fail(e);
			} finally {
				busy = false;
			}
		}
	};
}

export type NotificationPrefsVM = ReturnType<typeof createNotificationPrefs>;
