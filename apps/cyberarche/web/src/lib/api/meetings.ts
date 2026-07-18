import type { Document } from './documents';
import { get, post } from './http';

/** One of the caller's meeting recordings, enough to identify and pick one. */
export interface Recording {
	id: string;
	status: string;
	captured_at: string | null;
	headline: string | null;
}

/** The caller's recent meeting recordings (read with their delegated token). */
export const listRecordings = () => get<Recording[]>('/api/v1/meetings');

/** Structure a recording's transcript into a new document and return it. */
export const createMeetingNotes = (
	workspaceId: string,
	recordingId: string,
	teamspaceId?: string
) =>
	post<Document>(`/api/v1/workspaces/${workspaceId}/meeting-notes`, {
		recording_id: recordingId,
		teamspace_id: teamspaceId ?? null
	});
