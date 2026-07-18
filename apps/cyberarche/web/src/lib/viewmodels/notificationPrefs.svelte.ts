/** Notification preferences ViewModel (notifications spec): load the caller's
 * delivery toggles and flip one optimistically (PUT the whole set, roll back on
 * failure). In-app is always on and not represented here. */
import { getPrefs, updatePrefs, type NotificationPrefs } from '$lib/api/notificationPrefs';
import { ApiError } from '$lib/api/http';
import { disablePush, enablePush, getVapidPublicKey } from '$lib/push';

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
		if (e instanceof ApiError) error = `${e.status}: ${e.message}`;
		else if (e instanceof Error) error = e.message;
		else error = String(e);
	}

	/** Mirror the push preference to the browser: subscribe when enabling
	 * (throwing a friendly error when push is unavailable / permission denied),
	 * best-effort unsubscribe when disabling. The Web APIs live in $lib/push. */
	async function syncPushSubscription(enabled: boolean): Promise<void> {
		if (!enabled) {
			await disablePush();
			return;
		}
		const ok = await enablePush(await getVapidPublicKey());
		if (!ok) {
			throw new Error(
				'Push notifications are unavailable in this browser or permission was denied.'
			);
		}
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
			let persisted = false;
			try {
				prefs = await updatePrefs(prefs);
				persisted = true;
				if (key === 'push_enabled') await syncPushSubscription(prefs.push_enabled);
			} catch (e) {
				prefs = previous; // roll back the optimistic flip
				// A push-sync failure happens after the PUT already saved the new
				// value; re-persist the reverted preference so client and server agree.
				if (persisted) await updatePrefs(previous).catch(() => {});
				fail(e);
			} finally {
				busy = false;
			}
		}
	};
}

export type NotificationPrefsVM = ReturnType<typeof createNotificationPrefs>;
