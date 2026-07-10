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
});
