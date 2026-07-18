/** Meeting-notes ViewModel + modal singleton (ai-agent spec): list the caller's
 * meeting recordings and turn one into a new structured document. DOM-free —
 * the component only reads state and calls these methods. */

import type { Document } from '$lib/api/documents';
import { ApiError } from '$lib/api/http';
import { createMeetingNotes, listRecordings, type Recording } from '$lib/api/meetings';

/** Friendly message for the common failures (not signed in / not configured),
 * falling back to the server detail for anything else. */
function friendlyError(err: unknown): string {
	if (err instanceof ApiError) {
		if (err.status === 401) return 'Sign in again to access your meetings.';
		if (err.status === 422) return 'Meeting transcripts are not configured.';
		return err.detail;
	}
	return (err as Error).message;
}

export function createMeetingNotes_VM(workspaceId: string) {
	let recordings = $state<Recording[]>([]);
	let loading = $state(false);
	let error = $state<string | null>(null);
	/** id of the recording currently being turned into a document, if any. */
	let pendingId = $state<string | null>(null);

	return {
		get recordings() {
			return recordings;
		},
		get loading() {
			return loading;
		},
		get error() {
			return error;
		},
		get pendingId() {
			return pendingId;
		},

		/** Load the caller's recordings for the picker. */
		async load() {
			loading = true;
			error = null;
			try {
				recordings = await listRecordings();
			} catch (err) {
				error = friendlyError(err);
			} finally {
				loading = false;
			}
		},

		/** Generate a document from one recording; returns the new (private)
		 * document on success so the caller can add it to the sidebar and open it. */
		async generate(recordingId: string): Promise<Document | null> {
			if (pendingId) return null;
			pendingId = recordingId;
			error = null;
			try {
				return await createMeetingNotes(workspaceId, recordingId);
			} catch (err) {
				error = friendlyError(err);
				return null;
			} finally {
				pendingId = null;
			}
		}
	};
}

export type MeetingNotesVM = ReturnType<typeof createMeetingNotes_VM>;

/** Open/close state for the meeting-notes modal — a module singleton so the
 * sidebar button can open the modal the workspace layout renders (mirrors
 * settingsModal / workspaceChatOpen). */
export function createMeetingNotesModal() {
	let open = $state(false);

	return {
		get isOpen() {
			return open;
		},
		open() {
			open = true;
		},
		close() {
			open = false;
		}
	};
}

export const meetingNotesModal = createMeetingNotesModal();
