/** Meeting-notes ViewModel + modal singleton (ai-agent spec): list the caller's
 * meeting recordings and turn one into a new structured document. DOM-free —
 * the component only reads state and calls these methods. */

import type { Document } from '$lib/api/documents';
import { ApiError } from '$lib/api/http';
import { createMeetingNotes, listRecordings, type Recording } from '$lib/api/meetings';

/** Recordings grouped under one month/year. `key` is a sortable 'YYYY-MM' (or
 * 'undated'); `year`/`month0` (0-based) let the view format a localized label. */
export interface MonthGroup {
	key: string;
	year: number;
	month0: number;
	recordings: Recording[];
}

function capturedMs(recording: Recording): number {
	const t = recording.captured_at ? Date.parse(recording.captured_at) : NaN;
	return Number.isNaN(t) ? -Infinity : t;
}

/** Group recordings by capture month, newest month first and newest recording
 * first within each; undated recordings fall into a trailing 'undated' group.
 * Pure and deterministic (month keyed in UTC) so it is safe to unit-test. */
export function groupRecordingsByMonth(recordings: Recording[]): MonthGroup[] {
	const groups = new Map<string, MonthGroup>();
	for (const recording of recordings) {
		const ms = capturedMs(recording);
		const dated = ms !== -Infinity;
		const date = dated ? new Date(ms) : null;
		const key = date
			? `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, '0')}`
			: 'undated';
		let group = groups.get(key);
		if (!group) {
			group = {
				key,
				year: date ? date.getUTCFullYear() : 0,
				month0: date ? date.getUTCMonth() : 0,
				recordings: []
			};
			groups.set(key, group);
		}
		group.recordings.push(recording);
	}
	for (const group of groups.values()) {
		group.recordings.sort((a, b) => capturedMs(b) - capturedMs(a));
	}
	return [...groups.values()].sort((a, b) => {
		if (a.key === 'undated') return 1;
		if (b.key === 'undated') return -1;
		return a.key < b.key ? 1 : -1;
	});
}

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
	/** Month keys the user has collapsed in the picker (view state). */
	let collapsed = $state<Set<string>>(new Set());

	return {
		get recordings() {
			return recordings;
		},
		/** Recordings grouped by month, newest first (for the picker). */
		get groups(): MonthGroup[] {
			return groupRecordingsByMonth(recordings);
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

		/** Whether a month group is collapsed (all expanded by default). */
		isCollapsed(key: string): boolean {
			return collapsed.has(key);
		},

		/** Collapse or expand a month group. */
		toggleMonth(key: string): void {
			const next = new Set(collapsed);
			if (next.has(key)) next.delete(key);
			else next.add(key);
			collapsed = next;
		},

		/** Load the caller's recordings for the picker. */
		async load() {
			loading = true;
			error = null;
			try {
				recordings = await listRecordings();
				// Open the newest month by default and collapse the rest, so the
				// picker starts focused on the latest recordings.
				const keys = groupRecordingsByMonth(recordings).map((group) => group.key);
				collapsed = new Set(keys.slice(1));
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
