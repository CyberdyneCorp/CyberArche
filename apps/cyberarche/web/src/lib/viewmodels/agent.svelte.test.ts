import { beforeEach, describe, expect, it, vi } from 'vitest';

import { createAgentPanel } from './agent.svelte';

const BLOCK = (text: string) => ({ type: 'paragraph', data: { text } });

/** Replies with `body` while capturing calls so request shapes can be asserted. */
function capturingFetch(body: unknown) {
	const calls: Array<{ url: string; method: string; body: unknown }> = [];
	const fn = vi.fn(async (url: string, init?: RequestInit) => {
		calls.push({
			url,
			method: init?.method ?? 'GET',
			body:
				init?.body === undefined || typeof init.body !== 'string'
					? undefined
					: JSON.parse(init.body)
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

describe('agent panel ViewModel', () => {
	beforeEach(() => vi.unstubAllGlobals());

	it('an answer surfaces its tool calls (built-in + MCP) for the chat', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async () => ({
				ok: true,
				status: 200,
				json: async () => ({
					answer: 'Done.',
					blocks: [],
					tool_calls: [
						{
							name: 'rag_query',
							kind: 'builtin',
							connector: null,
							arguments: { query: 'specs' },
							result: 'passages…',
							ok: true
						},
						{
							name: 'github__create_issue',
							kind: 'mcp',
							connector: 'github',
							arguments: { title: 'Bug' },
							result: 'error: no auth',
							ok: false
						}
					]
				})
			})) as unknown as typeof fetch
		);

		const vm = createAgentPanel('doc-1');
		await vm.ask('do it');

		const last = vm.messages[vm.messages.length - 1];
		expect(last.role).toBe('agent');
		expect(last.text).toBe('Done.');
		expect(last.toolCalls?.map((c) => [c.name, c.kind, c.ok])).toEqual([
			['rag_query', 'builtin', true],
			['github__create_issue', 'mcp', false]
		]);
		expect(last.toolCalls?.[0].arguments).toEqual({ query: 'specs' });
	});

	it('sends recent conversation history so follow-ups have context', async () => {
		const bodies: Array<{ instruction: string; history: unknown }> = [];
		vi.stubGlobal(
			'fetch',
			vi.fn(async (_url: string, init?: RequestInit) => {
				bodies.push(JSON.parse(String(init?.body)));
				return {
					ok: true,
					status: 200,
					json: async () => ({ answer: 'A', blocks: [], tool_calls: [] })
				};
			}) as unknown as typeof fetch
		);

		const vm = createAgentPanel('doc-1');
		await vm.ask('create a plot');
		await vm.ask('insert the plot');

		// The second turn carries the first (user + agent) as history.
		expect(bodies[1].instruction).toBe('insert the plot');
		expect(bodies[1].history).toEqual([
			{ role: 'user', content: 'create a plot' },
			{ role: 'agent', content: 'A' }
		]);
	});

	it('ask forwards the reasoning flag', async () => {
		const { fn, calls } = capturingFetch({ answer: 'A', blocks: [], tool_calls: [] });
		vi.stubGlobal('fetch', fn);
		const vm = createAgentPanel('doc-1');

		await vm.ask('think hard', true);

		expect(calls[0].body).toMatchObject({ instruction: 'think hard', reasoning: true });
	});

	it('busy is true while a request is in flight and clears after', async () => {
		let resolve!: (value: unknown) => void;
		vi.stubGlobal(
			'fetch',
			vi.fn(() => new Promise((r) => (resolve = r))) as unknown as typeof fetch
		);
		const vm = createAgentPanel('doc-1');

		const pending = vm.ask('slow question');
		expect(vm.busy).toBe(true);
		expect(vm.messages).toEqual([{ role: 'user', text: 'slow question' }]);

		resolve({ ok: true, status: 200, json: async () => ({ answer: 'A', blocks: [], tool_calls: [] }) });
		await pending;
		expect(vm.busy).toBe(false);
	});

	it('a failed ask surfaces the error and keeps the user turn without a reply', async () => {
		vi.stubGlobal('fetch', failingFetch(500, 'model unavailable'));
		const vm = createAgentPanel('doc-1');

		await vm.ask('do it');

		expect(vm.error).toBe('500: model unavailable');
		expect(vm.busy).toBe(false);
		expect(vm.messages).toEqual([{ role: 'user', text: 'do it' }]);
	});

	it('a later success clears a previous error', async () => {
		vi.stubGlobal('fetch', failingFetch(500, 'boom'));
		const vm = createAgentPanel('doc-1');
		await vm.ask('first');
		expect(vm.error).toBe('500: boom');

		const { fn } = capturingFetch({ answer: 'A', blocks: [], tool_calls: [] });
		vi.stubGlobal('fetch', fn);
		await vm.ask('second');

		expect(vm.error).toBeNull();
	});

	it('summarize with no selection labels the whole document and previews block text', async () => {
		const { fn, calls } = capturingFetch({
			blocks: [BLOCK('First point.'), BLOCK('Second point.')],
			inserted: false
		});
		vi.stubGlobal('fetch', fn);
		const vm = createAgentPanel('doc-1');

		await vm.summarize();

		expect(calls[0].body).toEqual({ block_ids: null });
		expect(vm.messages[0]).toEqual({ role: 'user', text: 'Summarize this document' });
		const reply = vm.messages[1];
		expect(reply.text).toBe('First point.\n\nSecond point.');
		expect(reply.blocks).toHaveLength(2);
	});

	it('summarize labels a single selected block in the singular', async () => {
		const { fn, calls } = capturingFetch({ blocks: [BLOCK('S')], inserted: false });
		vi.stubGlobal('fetch', fn);
		const vm = createAgentPanel('doc-1');

		await vm.summarize(['b-1']);

		expect(calls[0].body).toEqual({ block_ids: ['b-1'] });
		expect(vm.messages[0].text).toBe('Summarize the selected block');
	});

	it('summarize labels multiple selected blocks in the plural', async () => {
		const { fn } = capturingFetch({ blocks: [BLOCK('S')], inserted: false });
		vi.stubGlobal('fetch', fn);
		const vm = createAgentPanel('doc-1');

		await vm.summarize(['b-1', 'b-2']);

		expect(vm.messages[0].text).toBe('Summarize the selected blocks');
	});

	it('summarize with an empty selection falls back to the whole document', async () => {
		const { fn, calls } = capturingFetch({ blocks: [BLOCK('S')], inserted: false });
		vi.stubGlobal('fetch', fn);
		const vm = createAgentPanel('doc-1');

		await vm.summarize([]);

		expect(vm.messages[0].text).toBe('Summarize this document');
		expect(calls[0].body).toEqual({ block_ids: [] });
	});

	it('previews a block count when the blocks carry no text', async () => {
		const { fn } = capturingFetch({
			blocks: [{ type: 'image', data: { url: '/x' } }, { type: 'divider' }],
			inserted: false
		});
		vi.stubGlobal('fetch', fn);
		const vm = createAgentPanel('doc-1');

		await vm.summarize();

		expect(vm.messages[1].text).toBe('2 block(s) ready');
	});

	it('draft labels the user turn and offers the drafted blocks', async () => {
		const { fn, calls } = capturingFetch({ blocks: [BLOCK('An intro.')], inserted: false });
		vi.stubGlobal('fetch', fn);
		const vm = createAgentPanel('doc-1');

		await vm.draft('an intro');

		expect(calls[0]).toMatchObject({
			url: '/api/v1/documents/doc-1/agent/draft',
			method: 'POST',
			body: { instruction: 'an intro' }
		});
		expect(vm.messages[0].text).toBe('Draft: an intro');
		expect(vm.messages[1].text).toBe('An intro.');
		expect(vm.messages[1].blocks).toEqual([BLOCK('An intro.')]);
	});

	it('insert without blocks is a no-op', async () => {
		const { fn } = capturingFetch({ blocks: [], inserted: true });
		vi.stubGlobal('fetch', fn);
		const vm = createAgentPanel('doc-1');

		await vm.insert({ role: 'agent', text: 'no payload' });
		await vm.insert({ role: 'agent', text: 'empty payload', blocks: [] });

		expect(fn).not.toHaveBeenCalled();
	});

	it('insert posts the blocks to the server and marks the message inserted', async () => {
		const { fn, calls } = capturingFetch({ answer: 'A', blocks: [BLOCK('P')], tool_calls: [] });
		vi.stubGlobal('fetch', fn);
		const vm = createAgentPanel('doc-1');
		await vm.ask('write P');

		await vm.insert(vm.messages[1]);

		expect(calls[1]).toMatchObject({
			url: '/api/v1/documents/doc-1/agent/blocks',
			method: 'POST',
			body: { blocks: [BLOCK('P')] }
		});
		expect(vm.messages[1].inserted).toBe(true);
		expect(vm.messages[0].inserted).toBeUndefined(); // only the inserted message flips
	});

	it('insert prefers the local CRDT peer edit when provided', async () => {
		const { fn } = capturingFetch({ answer: 'A', blocks: [BLOCK('P')], tool_calls: [] });
		vi.stubGlobal('fetch', fn);
		const insertLocal = vi.fn();
		const vm = createAgentPanel('doc-1', { insertLocal });
		await vm.ask('write P');

		await vm.insert(vm.messages[1]);

		expect(insertLocal).toHaveBeenCalledWith([BLOCK('P')]);
		expect(fn).toHaveBeenCalledTimes(1); // only the ask — no server insert
		expect(vm.messages[1].inserted).toBe(true);
	});

	it('replaceSelection requires a focused block', async () => {
		const { fn } = capturingFetch({ block_id: 'b-1' });
		vi.stubGlobal('fetch', fn);
		const vm = createAgentPanel('doc-1');

		await vm.replaceSelection({ role: 'agent', text: 'new text' }, null);

		expect(vm.error).toBe('Select a block in the document first.');
		expect(fn).not.toHaveBeenCalled();
	});

	it('replaceSelection patches the block text and marks the message inserted', async () => {
		const { fn, calls } = capturingFetch({ answer: 'new text', blocks: [], tool_calls: [] });
		vi.stubGlobal('fetch', fn);
		const vm = createAgentPanel('doc-1');
		await vm.ask('rewrite');

		await vm.replaceSelection(vm.messages[1], 'b-1');

		expect(calls[1]).toMatchObject({
			url: '/api/v1/documents/doc-1/agent/blocks/b-1',
			method: 'PATCH',
			body: { text: 'new text' }
		});
		expect(vm.messages[1].inserted).toBe(true);
		expect(vm.error).toBeNull();
	});

	it('copy writes the message text to the clipboard', async () => {
		const writeText = vi.fn(async () => undefined);
		vi.stubGlobal('navigator', { clipboard: { writeText } });
		const vm = createAgentPanel('doc-1');

		await vm.copy({ role: 'agent', text: 'copied text' });

		expect(writeText).toHaveBeenCalledWith('copied text');
	});

	it('ingest uploads the file and reports the added blocks', async () => {
		const { fn } = capturingFetch({ blocks: [BLOCK('a'), BLOCK('b')], inserted: true });
		vi.stubGlobal('fetch', fn);
		const vm = createAgentPanel('doc-1');
		const file = new File(['pdf-bytes'], 'notes.pdf', { type: 'application/pdf' });

		await vm.ingest(file);

		expect(vm.ingesting).toBe('done');
		expect(vm.error).toBeNull();
		expect(vm.messages).toEqual([
			{
				role: 'agent',
				text: 'Ingested notes.pdf — 2 block(s) added to the document and submitted to the knowledge base.'
			}
		]);
		const [url, init] = (fn as ReturnType<typeof vi.fn>).mock.calls[0];
		expect(url).toBe('/api/v1/documents/doc-1/agent/ingest');
		expect(init.body).toBeInstanceOf(FormData);
		expect(init.body.get('file')).toBe(file);
	});

	it('a failed ingest surfaces the error and resets to idle', async () => {
		vi.stubGlobal('fetch', failingFetch(415, 'unsupported file'));
		const vm = createAgentPanel('doc-1');

		await vm.ingest(new File(['x'], 'weird.bin'));

		expect(vm.ingesting).toBe('idle');
		expect(vm.error).toBe('415: unsupported file');
		expect(vm.messages).toEqual([]);
	});

	it('loadRuns populates the run history', async () => {
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
		const vm = createAgentPanel('doc-1');

		expect(vm.runs).toEqual([]);
		await vm.loadRuns();

		expect(calls[0].url).toBe('/api/v1/documents/doc-1/agent/runs');
		expect(vm.runs).toEqual([run]);
	});
});
