import { beforeEach, describe, expect, it, vi } from 'vitest';

import { createMeetingNotes_VM, groupRecordingsByMonth } from './meetingNotesModal.svelte';

const REC = (id: string, captured_at: string | null) => ({
	id,
	status: 'completed',
	captured_at,
	headline: id
});

describe('groupRecordingsByMonth', () => {
	it('groups by capture month, newest month and recording first', () => {
		const groups = groupRecordingsByMonth([
			REC('may-a', '2026-05-10T09:00:00Z'),
			REC('jun-old', '2026-06-02T09:00:00Z'),
			REC('jun-new', '2026-06-28T17:00:00Z')
		]);

		expect(groups.map((g) => g.key)).toEqual(['2026-06', '2026-05']);
		expect(groups[0]).toMatchObject({ year: 2026, month0: 5 });
		// newest recording first within the month
		expect(groups[0].recordings.map((r) => r.id)).toEqual(['jun-new', 'jun-old']);
		expect(groups[1].recordings.map((r) => r.id)).toEqual(['may-a']);
	});

	it('puts undated/unparseable recordings in a trailing group', () => {
		const groups = groupRecordingsByMonth([
			REC('none', null),
			REC('jun', '2026-06-15T12:00:00Z'),
			REC('bad', 'not-a-date')
		]);

		expect(groups.map((g) => g.key)).toEqual(['2026-06', 'undated']);
		expect(groups[1].recordings.map((r) => r.id).sort()).toEqual(['bad', 'none']);
	});

	it('returns nothing for no recordings', () => {
		expect(groupRecordingsByMonth([])).toEqual([]);
	});
});

/** Replies with `body` while capturing request shapes for assertions. */
function capturingFetch(body: unknown) {
	const calls: Array<{ url: string; body: unknown }> = [];
	const fn = vi.fn(async (url: string, init?: RequestInit) => {
		calls.push({
			url,
			body: typeof init?.body === 'string' ? JSON.parse(init.body) : undefined
		});
		return { ok: true, status: 200, json: async () => body };
	}) as unknown as typeof fetch;
	return { fn, calls };
}

function failingFetch(status: number, detail: string) {
	return vi.fn(async () => ({
		ok: false,
		status,
		json: async () => ({ detail })
	})) as unknown as typeof fetch;
}

describe('meeting-notes ViewModel', () => {
	beforeEach(() => vi.unstubAllGlobals());

	it('load fetches the recordings', async () => {
		const recordings = [
			{ id: 'rec-1', status: 'ready', captured_at: null, headline: 'Standup' }
		];
		const { fn, calls } = capturingFetch(recordings);
		vi.stubGlobal('fetch', fn);

		const vm = createMeetingNotes_VM('ws-1');
		await vm.load();

		expect(vm.recordings).toEqual(recordings);
		expect(vm.loading).toBe(false);
		expect(vm.error).toBeNull();
		expect(calls[0].url).toContain('/api/v1/meetings');
	});

	it('generate posts the recording and returns the new (private) document', async () => {
		const document = {
			id: 'doc-9',
			title: 'Standup',
			workspace_id: 'ws-1',
			teamspace_id: null,
			parent_id: null
		};
		const { fn, calls } = capturingFetch(document);
		vi.stubGlobal('fetch', fn);

		const vm = createMeetingNotes_VM('ws-1');
		const result = await vm.generate('rec-1');

		// Returns the whole document (created private: no teamspace) so the caller
		// can surface it under the sidebar's Private section without a reload.
		expect(result).toMatchObject({ id: 'doc-9', teamspace_id: null });
		expect(vm.pendingId).toBeNull();
		expect(vm.error).toBeNull();
		expect(calls[0].url).toContain('/api/v1/workspaces/ws-1/meeting-notes');
		expect(calls[0].body).toEqual({ recording_id: 'rec-1', teamspace_id: null });
	});

	it('maps a 422 to a friendly not-configured message and returns null', async () => {
		vi.stubGlobal('fetch', failingFetch(422, 'meeting transcripts are not configured'));
		const vm = createMeetingNotes_VM('ws-1');

		const result = await vm.generate('rec-1');

		expect(result).toBeNull();
		expect(vm.error).toBe('Meeting transcripts are not configured.');
		expect(vm.pendingId).toBeNull();
	});

	it('maps a 401 on load to a friendly sign-in message', async () => {
		vi.stubGlobal('fetch', failingFetch(401, 'missing bearer token'));
		const vm = createMeetingNotes_VM('ws-1');

		await vm.load();

		expect(vm.error).toBe('Sign in again to access your meetings.');
		expect(vm.recordings).toEqual([]);
	});
});
