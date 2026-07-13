import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from './http';
import { createWorkspace, getWorkspace, listWorkspaces } from './workspaces';

const WORKSPACE = {
	id: 'ws-1',
	name: 'Acme',
	created_by: 'alice',
	created_at: '2026-01-01T00:00:00Z',
	rag_project_slug: null
};

function mockFetch(status: number, body: unknown) {
	return vi.fn(async () => ({
		ok: status < 400,
		status,
		json: async () => body
	})) as unknown as typeof fetch;
}

describe('workspaces API client', () => {
	beforeEach(() => vi.restoreAllMocks());

	it('listWorkspaces GETs the collection', async () => {
		const fetchMock = mockFetch(200, [WORKSPACE]);
		vi.stubGlobal('fetch', fetchMock);

		expect(await listWorkspaces()).toEqual([WORKSPACE]);

		const [url, init] = (fetchMock as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
		expect(url).toBe('/api/v1/workspaces');
		expect(init.method).toBeUndefined(); // plain GET
	});

	it('createWorkspace POSTs the name as JSON', async () => {
		const fetchMock = mockFetch(200, WORKSPACE);
		vi.stubGlobal('fetch', fetchMock);

		expect(await createWorkspace('Acme')).toEqual(WORKSPACE);

		const [url, init] = (fetchMock as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
		expect(url).toBe('/api/v1/workspaces');
		expect(init.method).toBe('POST');
		expect(JSON.parse(String(init.body))).toEqual({ name: 'Acme' });
	});

	it('getWorkspace GETs by id', async () => {
		const fetchMock = mockFetch(200, WORKSPACE);
		vi.stubGlobal('fetch', fetchMock);

		expect(await getWorkspace('ws-1')).toEqual(WORKSPACE);

		const [url] = (fetchMock as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
		expect(url).toBe('/api/v1/workspaces/ws-1');
	});

	it('surfaces HTTP failures as ApiError', async () => {
		vi.stubGlobal('fetch', mockFetch(403, { detail: 'forbidden' }));

		await expect(getWorkspace('ws-1')).rejects.toThrowError(ApiError);
		await expect(listWorkspaces()).rejects.toMatchObject({ status: 403, detail: 'forbidden' });
	});
});
