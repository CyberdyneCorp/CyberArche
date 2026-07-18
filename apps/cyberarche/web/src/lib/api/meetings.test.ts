import { beforeEach, describe, expect, it, vi } from 'vitest';

import { createMeetingNotes, listRecordings } from './meetings';

/** Captures every request so the URL/method/body shape is asserted. */
function capturingFetch(body: unknown = null) {
	const calls: Array<{ url: string; method: string; body: unknown }> = [];
	const fn = vi.fn(async (url: string, init?: RequestInit) => {
		calls.push({
			url,
			method: init?.method ?? 'GET',
			body: init?.body ? JSON.parse(String(init.body)) : undefined
		});
		return { ok: true, status: 200, json: async () => body };
	}) as unknown as typeof fetch;
	return { fn, calls };
}

describe('meetings API client', () => {
	beforeEach(() => vi.restoreAllMocks());

	it('listRecordings GETs the meetings endpoint and returns the recordings', async () => {
		const recordings = [
			{ id: 'rec-1', status: 'ready', captured_at: '2026-07-01T10:00:00Z', headline: 'Standup' }
		];
		const { fn, calls } = capturingFetch(recordings);
		vi.stubGlobal('fetch', fn);

		expect(await listRecordings()).toEqual(recordings);
		expect(calls).toEqual([
			{ url: '/api/v1/meetings', method: 'GET', body: undefined }
		]);
	});

	it('createMeetingNotes POSTs the recording id and returns the new document', async () => {
		const doc = { id: 'doc-9', title: 'Standup' };
		const { fn, calls } = capturingFetch(doc);
		vi.stubGlobal('fetch', fn);

		expect(await createMeetingNotes('ws-1', 'rec-1')).toEqual(doc);
		expect(calls).toEqual([
			{
				url: '/api/v1/workspaces/ws-1/meeting-notes',
				method: 'POST',
				body: { recording_id: 'rec-1', teamspace_id: null }
			}
		]);
	});

	it('createMeetingNotes forwards a teamspace id when given', async () => {
		const { fn, calls } = capturingFetch({ id: 'doc-9' });
		vi.stubGlobal('fetch', fn);

		await createMeetingNotes('ws-1', 'rec-1', 'ts-2');
		expect(calls[0].body).toEqual({ recording_id: 'rec-1', teamspace_id: 'ts-2' });
	});
});
