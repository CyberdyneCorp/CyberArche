import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from './http';
import {
	createFolder,
	deleteFolder,
	folderDocuments,
	listFolders,
	listPrivate,
	moveToPrivate,
	moveToTeamspace,
	placeInFolder,
	renameFolder
} from './folders';

const FOLDER = {
	id: 'f-1',
	workspace_id: 'ws-1',
	name: 'Research',
	teamspace_id: 'ts-1',
	parent_folder_id: null,
	created_by: 'alice',
	created_at: '2026-01-01T00:00:00Z'
};

const DOC = {
	id: 'd-1',
	workspace_id: 'ws-1',
	title: 'Doc',
	parent_id: null,
	position: 0,
	created_by: 'alice',
	created_at: '2026-01-01T00:00:00Z',
	updated_at: '2026-01-01T00:00:00Z',
	trashed: false,
	teamspace_id: null
};

function mockFetch(status: number, body: unknown) {
	return vi.fn(async () => ({
		ok: status < 400,
		status,
		json: async () => body
	})) as unknown as typeof fetch;
}

function lastCall(fetchMock: typeof fetch): [string, RequestInit] {
	return (fetchMock as ReturnType<typeof vi.fn>).mock.calls.at(-1) as [string, RequestInit];
}

describe('folders API', () => {
	beforeEach(() => vi.restoreAllMocks());

	it('listFolders GETs the workspace folders', async () => {
		const fetchMock = mockFetch(200, [FOLDER]);
		vi.stubGlobal('fetch', fetchMock);

		expect(await listFolders('ws-1')).toEqual([FOLDER]);
		const [url, init] = lastCall(fetchMock);
		expect(url).toBe('/api/v1/workspaces/ws-1/folders');
		expect(init.method).toBeUndefined();
	});

	it('createFolder POSTs the name, teamspace and parent', async () => {
		const fetchMock = mockFetch(200, FOLDER);
		vi.stubGlobal('fetch', fetchMock);

		expect(await createFolder('ws-1', 'Research', 'ts-1', 'f-parent')).toEqual(FOLDER);
		const [url, init] = lastCall(fetchMock);
		expect(url).toBe('/api/v1/workspaces/ws-1/folders');
		expect(init.method).toBe('POST');
		expect(JSON.parse(init.body as string)).toEqual({
			name: 'Research',
			teamspace_id: 'ts-1',
			parent_folder_id: 'f-parent'
		});
	});

	it('createFolder defaults omitted teamspace and parent to null', async () => {
		const fetchMock = mockFetch(200, FOLDER);
		vi.stubGlobal('fetch', fetchMock);

		await createFolder('ws-1', 'Private stuff');
		expect(JSON.parse(lastCall(fetchMock)[1].body as string)).toEqual({
			name: 'Private stuff',
			teamspace_id: null,
			parent_folder_id: null
		});

		await createFolder('ws-1', 'Private stuff', null, null);
		expect(JSON.parse(lastCall(fetchMock)[1].body as string)).toEqual({
			name: 'Private stuff',
			teamspace_id: null,
			parent_folder_id: null
		});
	});

	it('renameFolder PATCHes the new name', async () => {
		const fetchMock = mockFetch(200, { ...FOLDER, name: 'Archive' });
		vi.stubGlobal('fetch', fetchMock);

		expect((await renameFolder('f-1', 'Archive')).name).toBe('Archive');
		const [url, init] = lastCall(fetchMock);
		expect(url).toBe('/api/v1/folders/f-1');
		expect(init.method).toBe('PATCH');
		expect(JSON.parse(init.body as string)).toEqual({ name: 'Archive' });
	});

	it('deleteFolder DELETEs and resolves undefined on 204', async () => {
		const fetchMock = mockFetch(204, undefined);
		vi.stubGlobal('fetch', fetchMock);

		expect(await deleteFolder('f-1')).toBeUndefined();
		const [url, init] = lastCall(fetchMock);
		expect(url).toBe('/api/v1/folders/f-1');
		expect(init.method).toBe('DELETE');
	});

	it('folderDocuments GETs the folder contents', async () => {
		const fetchMock = mockFetch(200, [DOC]);
		vi.stubGlobal('fetch', fetchMock);

		expect(await folderDocuments('f-1')).toEqual([DOC]);
		expect(lastCall(fetchMock)[0]).toBe('/api/v1/folders/f-1/documents');
	});

	it('placeInFolder POSTs the target folder (or null to unfile)', async () => {
		const fetchMock = mockFetch(200, DOC);
		vi.stubGlobal('fetch', fetchMock);

		expect(await placeInFolder('d-1', 'f-1')).toEqual(DOC);
		let [url, init] = lastCall(fetchMock);
		expect(url).toBe('/api/v1/documents/d-1/location');
		expect(init.method).toBe('POST');
		expect(JSON.parse(init.body as string)).toEqual({ folder_id: 'f-1' });

		await placeInFolder('d-1', null);
		[url, init] = lastCall(fetchMock);
		expect(JSON.parse(init.body as string)).toEqual({ folder_id: null });
	});

	it('moveToTeamspace POSTs the target teamspace', async () => {
		const fetchMock = mockFetch(200, { ...DOC, teamspace_id: 'ts-1' });
		vi.stubGlobal('fetch', fetchMock);

		expect((await moveToTeamspace('d-1', 'ts-1')).teamspace_id).toBe('ts-1');
		const [url, init] = lastCall(fetchMock);
		expect(url).toBe('/api/v1/documents/d-1/location');
		expect(JSON.parse(init.body as string)).toEqual({ teamspace_id: 'ts-1' });
	});

	it('moveToPrivate POSTs an empty location', async () => {
		const fetchMock = mockFetch(200, DOC);
		vi.stubGlobal('fetch', fetchMock);

		expect(await moveToPrivate('d-1')).toEqual(DOC);
		const [url, init] = lastCall(fetchMock);
		expect(url).toBe('/api/v1/documents/d-1/location');
		expect(init.method).toBe('POST');
		expect(JSON.parse(init.body as string)).toEqual({});
	});

	it('listPrivate GETs the private documents', async () => {
		const fetchMock = mockFetch(200, [DOC]);
		vi.stubGlobal('fetch', fetchMock);

		expect(await listPrivate('ws-1')).toEqual([DOC]);
		expect(lastCall(fetchMock)[0]).toBe('/api/v1/workspaces/ws-1/private');
	});

	it('surfaces an ApiError on a denied mutation', async () => {
		vi.stubGlobal('fetch', mockFetch(403, { detail: 'not allowed' }));

		await expect(createFolder('ws-1', 'Nope')).rejects.toThrow(ApiError);
		await expect(deleteFolder('f-1')).rejects.toThrow('403: not allowed');
	});
});
