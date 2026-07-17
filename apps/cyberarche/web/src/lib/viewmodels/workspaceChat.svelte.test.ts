import { beforeEach, describe, expect, it, vi } from 'vitest';

import { createWorkspaceChat } from './workspaceChat.svelte';

/** Replies with `body` while capturing request shapes for assertions. */
function capturingFetch(body: unknown) {
	const calls: Array<{ url: string; body: unknown }> = [];
	const fn = vi.fn(async (url: string, init?: RequestInit) => {
		calls.push({
			url,
			body: typeof init?.body === 'string' ? JSON.parse(init.body) : undefined
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

describe('workspace chat ViewModel', () => {
	beforeEach(() => vi.unstubAllGlobals());

	it('send appends the user turn then the assistant answer with sources', async () => {
		const { fn, calls } = capturingFetch({
			answer: 'It launches March 3.',
			sources: [{ id: 'doc-1', title: 'Roadmap' }]
		});
		vi.stubGlobal('fetch', fn);

		const chat = createWorkspaceChat('ws-1');
		await chat.send('When is launch?');

		expect(chat.messages).toHaveLength(2);
		expect(chat.messages[0]).toEqual({ role: 'user', content: 'When is launch?' });
		expect(chat.messages[1].role).toBe('assistant');
		expect(chat.messages[1].content).toBe('It launches March 3.');
		expect(chat.messages[1].sources).toEqual([{ id: 'doc-1', title: 'Roadmap' }]);
		expect(chat.busy).toBe(false);
		expect(chat.error).toBeNull();
		// It hit the workspace chat endpoint.
		expect(calls[0].url).toContain('/api/v1/workspaces/ws-1/chat');
	});

	it('sends prior turns as history (snapshot taken before the new user turn)', async () => {
		vi.stubGlobal('fetch', capturingFetch({ answer: 'first', sources: [] }).fn);
		const chat = createWorkspaceChat('ws-1');
		await chat.send('one');

		const second = capturingFetch({ answer: 'second', sources: [] });
		vi.stubGlobal('fetch', second.fn);
		await chat.send('two');

		// History carries the first exchange, not the just-typed 'two'.
		expect(second.calls[0].body).toMatchObject({
			instruction: 'two',
			history: [
				{ role: 'user', content: 'one' },
				{ role: 'assistant', content: 'first' }
			]
		});
	});

	it('sets error on failure and keeps the user turn', async () => {
		vi.stubGlobal('fetch', failingFetch(500, 'boom'));
		const chat = createWorkspaceChat('ws-1');

		await chat.send('hello');

		expect(chat.error).toContain('boom');
		expect(chat.busy).toBe(false);
		// The user turn stays; only the assistant reply is missing.
		expect(chat.messages).toEqual([{ role: 'user', content: 'hello' }]);
	});

	it('ignores empty input', async () => {
		const { fn } = capturingFetch({ answer: 'x', sources: [] });
		vi.stubGlobal('fetch', fn);
		const chat = createWorkspaceChat('ws-1');

		await chat.send('   ');

		expect(chat.messages).toHaveLength(0);
		expect(fn).not.toHaveBeenCalled();
	});
});
