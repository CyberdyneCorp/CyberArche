import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
	addFavorite,
	addTeamspaceMember,
	createTeamspace,
	deleteTeamspace,
	listFavorites,
	listTeamspaces,
	removeFavorite,
	removeTeamspaceMember,
	teamspaceDocuments,
	teamspaceMembers
} from './teamspaces';

const TEAMSPACE = {
	id: 'ts-1',
	workspace_id: 'ws-1',
	name: 'Tessera',
	icon: 'T',
	created_at: '2026-01-01T00:00:00Z'
};

const DOCUMENT = {
	id: 'doc-1',
	workspace_id: 'ws-1',
	title: 'Notes',
	parent_id: null,
	position: 0,
	created_by: 'alice',
	created_at: '2026-01-01T00:00:00Z',
	updated_at: '2026-01-01T00:00:00Z',
	trashed: false,
	teamspace_id: 'ts-1'
};

/** Captures every request so each client's URL/method/body shape is asserted. */
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

describe('teamspaces API client', () => {
	beforeEach(() => vi.restoreAllMocks());

	it('listTeamspaces GETs the workspace teamspaces', async () => {
		const { fn, calls } = capturingFetch([TEAMSPACE]);
		vi.stubGlobal('fetch', fn);

		expect(await listTeamspaces('ws-1')).toEqual([TEAMSPACE]);
		expect(calls).toEqual([
			{ url: '/api/v1/workspaces/ws-1/teamspaces', method: 'GET', body: undefined }
		]);
	});

	it('createTeamspace POSTs the name with the default icon', async () => {
		const { fn, calls } = capturingFetch(TEAMSPACE);
		vi.stubGlobal('fetch', fn);

		expect(await createTeamspace('ws-1', 'Tessera')).toEqual(TEAMSPACE);
		expect(calls).toEqual([
			{
				url: '/api/v1/workspaces/ws-1/teamspaces',
				method: 'POST',
				body: { name: 'Tessera', icon: 'T' }
			}
		]);
	});

	it('createTeamspace passes a custom icon', async () => {
		const { fn, calls } = capturingFetch({ ...TEAMSPACE, icon: 'X' });
		vi.stubGlobal('fetch', fn);

		await createTeamspace('ws-1', 'Tessera', 'X');

		expect(calls[0].body).toEqual({ name: 'Tessera', icon: 'X' });
	});

	it('teamspaceDocuments GETs the teamspace documents', async () => {
		const { fn, calls } = capturingFetch([DOCUMENT]);
		vi.stubGlobal('fetch', fn);

		expect(await teamspaceDocuments('ts-1')).toEqual([DOCUMENT]);
		expect(calls).toEqual([
			{ url: '/api/v1/teamspaces/ts-1/documents', method: 'GET', body: undefined }
		]);
	});

	it('deleteTeamspace DELETEs the teamspace', async () => {
		const { fn, calls } = capturingFetch();
		vi.stubGlobal('fetch', fn);

		await deleteTeamspace('ts-1');

		expect(calls).toEqual([{ url: '/api/v1/teamspaces/ts-1', method: 'DELETE', body: undefined }]);
	});

	it('teamspaceMembers GETs the member list', async () => {
		const member = { user_id: 'bob', role: 'editor', granted_at: '2026-01-01T00:00:00Z' };
		const { fn, calls } = capturingFetch([member]);
		vi.stubGlobal('fetch', fn);

		expect(await teamspaceMembers('ts-1')).toEqual([member]);
		expect(calls).toEqual([
			{ url: '/api/v1/teamspaces/ts-1/members', method: 'GET', body: undefined }
		]);
	});

	it('addTeamspaceMember POSTs the user and role', async () => {
		const member = { user_id: 'bob', role: 'viewer', granted_at: '2026-01-01T00:00:00Z' };
		const { fn, calls } = capturingFetch(member);
		vi.stubGlobal('fetch', fn);

		expect(await addTeamspaceMember('ts-1', 'bob', 'viewer')).toEqual(member);
		expect(calls).toEqual([
			{
				url: '/api/v1/teamspaces/ts-1/members',
				method: 'POST',
				body: { user_id: 'bob', role: 'viewer' }
			}
		]);
	});

	it('removeTeamspaceMember DELETEs the specific member', async () => {
		const { fn, calls } = capturingFetch();
		vi.stubGlobal('fetch', fn);

		await removeTeamspaceMember('ts-1', 'bob');

		expect(calls).toEqual([
			{ url: '/api/v1/teamspaces/ts-1/members/bob', method: 'DELETE', body: undefined }
		]);
	});

	it('listFavorites GETs the favourites collection', async () => {
		const { fn, calls } = capturingFetch([DOCUMENT]);
		vi.stubGlobal('fetch', fn);

		expect(await listFavorites()).toEqual([DOCUMENT]);
		expect(calls).toEqual([{ url: '/api/v1/favorites', method: 'GET', body: undefined }]);
	});

	it('addFavorite POSTs the document id', async () => {
		const { fn, calls } = capturingFetch();
		vi.stubGlobal('fetch', fn);

		await addFavorite('doc-1');

		expect(calls).toEqual([
			{ url: '/api/v1/favorites', method: 'POST', body: { document_id: 'doc-1' } }
		]);
	});

	it('removeFavorite DELETEs the specific favourite', async () => {
		const { fn, calls } = capturingFetch();
		vi.stubGlobal('fetch', fn);

		await removeFavorite('doc-1');

		expect(calls).toEqual([{ url: '/api/v1/favorites/doc-1', method: 'DELETE', body: undefined }]);
	});
});
