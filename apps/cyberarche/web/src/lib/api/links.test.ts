import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from './http';
import {
	folderGraph,
	folderInferredGraph,
	teamspaceGraph,
	teamspaceInferredGraph
} from './links';

const GRAPH = {
	nodes: [
		{ id: 'd-1', title: 'Alpha' },
		{ id: 'd-2', title: 'Beta' }
	],
	edges: [
		{
			source: 'd-1',
			target: 'd-2',
			type: 'links_to',
			confidence: 1,
			evidence: '',
			inferred: false
		}
	]
};

function mockFetch(status: number, body: unknown) {
	return vi.fn(async () => ({
		ok: status < 400,
		status,
		json: async () => body
	})) as unknown as typeof fetch;
}

describe('links API', () => {
	beforeEach(() => vi.restoreAllMocks());

	it('teamspaceGraph GETs the teamspace graph', async () => {
		const fetchMock = mockFetch(200, GRAPH);
		vi.stubGlobal('fetch', fetchMock);

		expect(await teamspaceGraph('ts-1')).toEqual(GRAPH);
		const [url, init] = (fetchMock as ReturnType<typeof vi.fn>).mock.calls[0];
		expect(url).toBe('/api/v1/teamspaces/ts-1/graph');
		expect(init.method).toBeUndefined();
	});

	it('folderGraph GETs the folder graph', async () => {
		const fetchMock = mockFetch(200, GRAPH);
		vi.stubGlobal('fetch', fetchMock);

		expect(await folderGraph('f-1')).toEqual(GRAPH);
		expect((fetchMock as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe(
			'/api/v1/folders/f-1/graph'
		);
	});

	it('teamspaceInferredGraph GETs the inferred teamspace graph', async () => {
		const fetchMock = mockFetch(200, GRAPH);
		vi.stubGlobal('fetch', fetchMock);

		expect(await teamspaceInferredGraph('ts-1')).toEqual(GRAPH);
		expect((fetchMock as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe(
			'/api/v1/teamspaces/ts-1/graph/inferred'
		);
	});

	it('folderInferredGraph GETs the inferred folder graph', async () => {
		const fetchMock = mockFetch(200, GRAPH);
		vi.stubGlobal('fetch', fetchMock);

		expect(await folderInferredGraph('f-1')).toEqual(GRAPH);
		expect((fetchMock as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe(
			'/api/v1/folders/f-1/graph/inferred'
		);
	});

	it('surfaces an ApiError when the graph is inaccessible', async () => {
		vi.stubGlobal('fetch', mockFetch(403, { detail: 'not a member' }));

		await expect(teamspaceGraph('ts-1')).rejects.toThrow(ApiError);
		await expect(folderGraph('f-1')).rejects.toThrow('403: not a member');
	});
});
