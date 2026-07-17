import { beforeEach, describe, expect, it, vi } from 'vitest';

import { askKnowledge, searchContent } from './search';

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

describe('search API client', () => {
	beforeEach(() => vi.restoreAllMocks());

	it('searchContent URL-encodes the query and returns the hits', async () => {
		const hits = [{ id: 'doc-1', title: 'Notes', field: 'content', snippet: '…launch…' }];
		const { fn, calls } = capturingFetch(hits);
		vi.stubGlobal('fetch', fn);

		expect(await searchContent('ws-1', 'road map')).toEqual(hits);
		expect(calls).toEqual([
			{
				url: '/api/v1/workspaces/ws-1/search/content?q=road+map',
				method: 'GET',
				body: undefined
			}
		]);
	});

	it('askKnowledge POSTs the question to the workspace RAG endpoint', async () => {
		const answer = { result: 'The launch is in March.', mode: 'hybrid' };
		const { fn, calls } = capturingFetch(answer);
		vi.stubGlobal('fetch', fn);

		expect(await askKnowledge('ws-1', 'When is launch?')).toEqual(answer);
		expect(calls).toEqual([
			{
				url: '/api/v1/workspaces/ws-1/knowledge/query',
				method: 'POST',
				body: { query: 'When is launch?' }
			}
		]);
	});
});
