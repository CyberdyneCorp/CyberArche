import { describe, expect, it, vi } from 'vitest';

import { createAgentPanel } from './agent.svelte';

describe('agent panel ViewModel', () => {
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
});
