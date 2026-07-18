import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
	askAgent,
	continueWriting,
	draftContent,
	ingestFile,
	insertBlocks,
	listAgentRuns,
	replaceBlockText,
	summarizeDocument,
	transformText
} from './agent';
import { ApiError } from './http';

const BLOCKS = { blocks: [{ type: 'paragraph', data: { text: 'hi' } }], inserted: false };

/** Captures fetch calls and replies with `body` so request shapes can be asserted. */
function capturingFetch(body: unknown) {
	const calls: Array<{ url: string; method: string; body: unknown }> = [];
	const fn = vi.fn(async (url: string, init?: RequestInit) => {
		calls.push({
			url,
			method: init?.method ?? 'GET',
			body: init?.body === undefined ? undefined : JSON.parse(String(init.body))
		});
		return { ok: true, status: 200, json: async () => body };
	}) as unknown as typeof fetch;
	return { fn, calls };
}

describe('agent API client', () => {
	beforeEach(() => vi.restoreAllMocks());

	it('askAgent POSTs the instruction, defaulting history and reasoning', async () => {
		const answer = { answer: 'Done.', blocks: [], tool_calls: [] };
		const { fn, calls } = capturingFetch(answer);
		vi.stubGlobal('fetch', fn);

		const result = await askAgent('doc-1', 'summarize this');

		expect(calls).toEqual([
			{
				url: '/api/v1/documents/doc-1/agent/ask',
				method: 'POST',
				body: { instruction: 'summarize this', history: [], reasoning: false }
			}
		]);
		expect(result).toEqual(answer);
	});

	it('askAgent sends the conversation history and the reasoning flag', async () => {
		const { fn, calls } = capturingFetch({ answer: 'A', blocks: [], tool_calls: [] });
		vi.stubGlobal('fetch', fn);
		const history = [
			{ role: 'user' as const, content: 'make a plot' },
			{ role: 'agent' as const, content: 'Here it is.' }
		];

		await askAgent('doc-1', 'insert the plot', history, true);

		expect(calls[0].body).toEqual({ instruction: 'insert the plot', history, reasoning: true });
	});

	it('summarizeDocument POSTs null block_ids for a whole-document summary', async () => {
		const { fn, calls } = capturingFetch(BLOCKS);
		vi.stubGlobal('fetch', fn);

		const result = await summarizeDocument('doc-1');

		expect(calls).toEqual([
			{
				url: '/api/v1/documents/doc-1/agent/summarize',
				method: 'POST',
				body: { block_ids: null }
			}
		]);
		expect(result).toEqual(BLOCKS);
	});

	it('summarizeDocument scopes to the selected block ids', async () => {
		const { fn, calls } = capturingFetch(BLOCKS);
		vi.stubGlobal('fetch', fn);

		await summarizeDocument('doc-1', ['b-1', 'b-2']);

		expect(calls[0].body).toEqual({ block_ids: ['b-1', 'b-2'] });
	});

	it('draftContent POSTs the instruction to the draft endpoint', async () => {
		const { fn, calls } = capturingFetch(BLOCKS);
		vi.stubGlobal('fetch', fn);

		const result = await draftContent('doc-1', 'an intro paragraph');

		expect(calls).toEqual([
			{
				url: '/api/v1/documents/doc-1/agent/draft',
				method: 'POST',
				body: { instruction: 'an intro paragraph' }
			}
		]);
		expect(result).toEqual(BLOCKS);
	});

	it('insertBlocks POSTs the blocks payload', async () => {
		const { fn, calls } = capturingFetch({ blocks: [], inserted: true });
		vi.stubGlobal('fetch', fn);
		const blocks = [{ type: 'paragraph', data: { text: 'hi' } }];

		await insertBlocks('doc-1', blocks);

		expect(calls).toEqual([
			{ url: '/api/v1/documents/doc-1/agent/blocks', method: 'POST', body: { blocks } }
		]);
	});

	it('ingestFile POSTs the file as multipart form data', async () => {
		const fetchMock = vi.fn(async () => ({
			ok: true,
			status: 200,
			json: async () => BLOCKS
		})) as unknown as typeof fetch;
		vi.stubGlobal('fetch', fetchMock);
		const file = new File(['pdf-bytes'], 'notes.pdf', { type: 'application/pdf' });

		const result = await ingestFile('doc-1', file);

		expect(result).toEqual(BLOCKS);
		const [url, init] = (fetchMock as ReturnType<typeof vi.fn>).mock.calls[0];
		expect(url).toBe('/api/v1/documents/doc-1/agent/ingest');
		expect(init.method).toBe('POST');
		expect(init.body).toBeInstanceOf(FormData);
		expect(init.body.get('file')).toBe(file);
		// The Content-Type must stay unset so fetch adds the multipart boundary.
		expect(new Headers(init.headers).get('Content-Type')).toBeNull();
	});

	it('listAgentRuns GETs the run history', async () => {
		const run = {
			id: 'run-1',
			user_id: 'alice',
			model: 'claude',
			prompt: 'summarize',
			tools_used: ['rag_query'],
			outcome: 'ok',
			started_at: '2026-01-01T00:00:00Z'
		};
		const { fn, calls } = capturingFetch([run]);
		vi.stubGlobal('fetch', fn);

		const runs = await listAgentRuns('doc-1');

		expect(calls).toEqual([
			{ url: '/api/v1/documents/doc-1/agent/runs', method: 'GET', body: undefined }
		]);
		expect(runs).toEqual([run]);
	});

	it('replaceBlockText PATCHes the block with the new text', async () => {
		const { fn, calls } = capturingFetch({ block_id: 'b-1' });
		vi.stubGlobal('fetch', fn);

		const result = await replaceBlockText('doc-1', 'b-1', 'rewritten');

		expect(calls).toEqual([
			{
				url: '/api/v1/documents/doc-1/agent/blocks/b-1',
				method: 'PATCH',
				body: { text: 'rewritten' }
			}
		]);
		expect(result).toEqual({ block_id: 'b-1' });
	});

	it('transformText POSTs the action, selection, and null target', async () => {
		const { fn, calls } = capturingFetch({ text: 'polished text' });
		vi.stubGlobal('fetch', fn);

		const result = await transformText('doc-1', 'rewrite', 'raw text');

		expect(calls).toEqual([
			{
				url: '/api/v1/documents/doc-1/agent/transform',
				method: 'POST',
				body: { action: 'rewrite', text: 'raw text', target: null }
			}
		]);
		expect(result).toEqual({ text: 'polished text' });
	});

	it('transformText forwards the translation target language', async () => {
		const { fn, calls } = capturingFetch({ text: 'texto' });
		vi.stubGlobal('fetch', fn);

		await transformText('doc-1', 'translate', 'text', 'Español');

		expect(calls[0].body).toEqual({ action: 'translate', text: 'text', target: 'Español' });
	});

	it('continueWriting POSTs the preceding text to the continue endpoint', async () => {
		const { fn, calls } = capturingFetch({ text: ' and then it ended.' });
		vi.stubGlobal('fetch', fn);

		const result = await continueWriting('doc-1', 'The story began');

		expect(calls).toEqual([
			{
				url: '/api/v1/documents/doc-1/agent/continue',
				method: 'POST',
				body: { preceding_text: 'The story began' }
			}
		]);
		expect(result).toEqual({ text: ' and then it ended.' });
	});

	it('surfaces an ApiError on rejection', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async () => ({
				ok: false,
				status: 403,
				json: async () => ({ detail: 'not a member' })
			})) as unknown as typeof fetch
		);

		await expect(askAgent('doc-1', 'x')).rejects.toThrow(ApiError);
		await expect(askAgent('doc-1', 'x')).rejects.toThrow('403: not a member');
	});
});
