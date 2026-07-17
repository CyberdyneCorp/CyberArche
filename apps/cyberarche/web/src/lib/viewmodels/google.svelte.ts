/** Google Workspace connector ViewModel (google-workspace-connector spec):
 * show status and connect (per tool-group consent) / disconnect a Google account. */
import {
	disconnectGoogle,
	getGoogleConnectUrl,
	getGoogleStatus,
	type GoogleStatus
} from '$lib/api/google';
import { ApiError } from '$lib/api/http';

// Read-only everywhere except Calendar (the one writable surface).
export const GOOGLE_GROUPS = [
	{ id: 'gmail_read', label: 'Gmail (read-only)' },
	{ id: 'calendar', label: 'Calendar (read + create events)' },
	{ id: 'drive', label: 'Docs & Drive (read-only)' },
	{ id: 'sheets', label: 'Sheets (read-only)' },
	{ id: 'slides', label: 'Slides (read-only)' }
];

export function createGoogle(workspaceId: string) {
	let status = $state<GoogleStatus | null>(null);
	let error = $state<string | null>(null);

	function fail(e: unknown): void {
		error = e instanceof ApiError ? `${e.status}: ${e.message}` : String(e);
	}

	return {
		get status() {
			return status;
		},
		get error() {
			return error;
		},

		async load(): Promise<void> {
			try {
				status = await getGoogleStatus(workspaceId);
			} catch (e) {
				fail(e);
			}
		},

		/** Redirect the browser to Google's consent screen for the chosen groups. */
		async connect(groups: string[]): Promise<void> {
			if (!groups.length) return;
			try {
				const { url } = await getGoogleConnectUrl(workspaceId, groups);
				window.location.href = url;
			} catch (e) {
				fail(e);
			}
		},

		async disconnect(): Promise<void> {
			try {
				await disconnectGoogle(workspaceId);
				await this.load();
			} catch (e) {
				fail(e);
			}
		}
	};
}

export type GoogleVM = ReturnType<typeof createGoogle>;
