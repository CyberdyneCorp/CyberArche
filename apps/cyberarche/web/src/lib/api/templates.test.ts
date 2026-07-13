import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from './http';
import {
	deleteTemplate,
	instantiateTemplate,
	listTemplates,
	saveTemplate
} from './templates';

const TEMPLATE = {
	id: 'tpl-1',
	name: 'Meeting notes',
	created_by: 'alice',
	created_at: '2026-01-01T00:00:00Z',
	block_count: 4
};

const DOC = {
	id: 'd-1',
	workspace_id: 'ws-1',
	title: 'From template',
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

describe('templates API', () => {
	beforeEach(() => vi.restoreAllMocks());

	it('listTemplates GETs the workspace templates', async () => {
		const fetchMock = mockFetch(200, [TEMPLATE]);
		vi.stubGlobal('fetch', fetchMock);

		expect(await listTemplates('ws-1')).toEqual([TEMPLATE]);
		const [url, init] = lastCall(fetchMock);
		expect(url).toBe('/api/v1/workspaces/ws-1/templates');
		expect(init.method).toBeUndefined();
	});

	it('saveTemplate POSTs the name and source document', async () => {
		const fetchMock = mockFetch(200, TEMPLATE);
		vi.stubGlobal('fetch', fetchMock);

		expect(await saveTemplate('ws-1', 'Meeting notes', 'd-1')).toEqual(TEMPLATE);
		const [url, init] = lastCall(fetchMock);
		expect(url).toBe('/api/v1/workspaces/ws-1/templates');
		expect(init.method).toBe('POST');
		expect(JSON.parse(init.body as string)).toEqual({
			name: 'Meeting notes',
			document_id: 'd-1'
		});
	});

	it('instantiateTemplate POSTs the title and teamspace', async () => {
		const fetchMock = mockFetch(200, DOC);
		vi.stubGlobal('fetch', fetchMock);

		expect(await instantiateTemplate('ws-1', 'tpl-1', 'Weekly sync', 'ts-1')).toEqual(DOC);
		const [url, init] = lastCall(fetchMock);
		expect(url).toBe('/api/v1/workspaces/ws-1/templates/tpl-1/instantiate');
		expect(init.method).toBe('POST');
		expect(JSON.parse(init.body as string)).toEqual({
			title: 'Weekly sync',
			teamspace_id: 'ts-1'
		});
	});

	it('instantiateTemplate defaults an omitted teamspace to null', async () => {
		const fetchMock = mockFetch(200, DOC);
		vi.stubGlobal('fetch', fetchMock);

		await instantiateTemplate('ws-1', 'tpl-1', 'Private page');
		expect(JSON.parse(lastCall(fetchMock)[1].body as string)).toEqual({
			title: 'Private page',
			teamspace_id: null
		});

		await instantiateTemplate('ws-1', 'tpl-1', 'Private page', null);
		expect(JSON.parse(lastCall(fetchMock)[1].body as string)).toEqual({
			title: 'Private page',
			teamspace_id: null
		});
	});

	it('deleteTemplate DELETEs and resolves undefined on 204', async () => {
		const fetchMock = mockFetch(204, undefined);
		vi.stubGlobal('fetch', fetchMock);

		expect(await deleteTemplate('tpl-1')).toBeUndefined();
		const [url, init] = lastCall(fetchMock);
		expect(url).toBe('/api/v1/templates/tpl-1');
		expect(init.method).toBe('DELETE');
	});

	it('surfaces an ApiError on a denied save', async () => {
		vi.stubGlobal('fetch', mockFetch(403, { detail: 'viewer role' }));

		await expect(saveTemplate('ws-1', 'Nope', 'd-1')).rejects.toThrow(ApiError);
		await expect(listTemplates('ws-1')).rejects.toThrow('403: viewer role');
	});
});
