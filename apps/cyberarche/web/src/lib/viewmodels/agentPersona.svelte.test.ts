import { beforeEach, describe, expect, it, vi } from 'vitest';

import { createAgentPersona } from './agentPersona.svelte';

const MEMORY = (id: string, text: string) => ({
	id,
	text,
	created_by: 'alice',
	created_at: '2026-01-01T00:00:00Z',
	updated_at: '2026-01-01T00:00:00Z'
});

/** Routes fetch by URL+method so the VM's real request shapes are exercised. */
function routedFetch(routes: Record<string, unknown>) {
	return vi.fn(async (url: string, init?: RequestInit) => {
		const key = `${init?.method ?? 'GET'} ${url}`;
		const body = routes[key];
		if (body === undefined) throw new Error(`unrouted: ${key}`);
		return { ok: true, status: 200, json: async () => body };
	}) as unknown as typeof fetch;
}

describe('agent persona ViewModel', () => {
	beforeEach(() => vi.restoreAllMocks());

	it('load populates instructions and memories', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/workspaces/ws-1/agent/instructions': {
					workspace: 'Be terse',
					personal: 'Call me Leo'
				},
				'GET /api/v1/workspaces/ws-1/agent/memories': [MEMORY('m-1', 'Prefers dark mode')]
			})
		);
		const vm = createAgentPersona('ws-1');
		await vm.load();

		expect(vm.workspaceText).toBe('Be terse');
		expect(vm.personalText).toBe('Call me Leo');
		expect(vm.memories.map((m) => m.id)).toEqual(['m-1']);
		expect(vm.error).toBeNull();
	});

	it('load maps null instruction layers to empty strings', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/workspaces/ws-1/agent/instructions': { workspace: null, personal: null },
				'GET /api/v1/workspaces/ws-1/agent/memories': []
			})
		);
		const vm = createAgentPersona('ws-1');
		await vm.load();

		expect(vm.workspaceText).toBe('');
		expect(vm.personalText).toBe('');
		expect(vm.memories).toEqual([]);
	});

	it('load surfaces an ApiError with its status', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async () => ({
				ok: false,
				status: 403,
				json: async () => ({ detail: 'nope' })
			})) as unknown as typeof fetch
		);
		const vm = createAgentPersona('ws-1');
		await vm.load();

		expect(vm.error).toMatch(/403/);
		expect(vm.error).toMatch(/nope/);
	});

	it('load stringifies a non-Api failure', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async () => {
				throw new Error('network down');
			}) as unknown as typeof fetch
		);
		const vm = createAgentPersona('ws-1');
		await vm.load();

		expect(vm.error).toBe('Error: network down');
	});

	it('saveInstructions PUTs the workspace text when non-empty', async () => {
		const fetchMock = routedFetch({
			'PUT /api/v1/workspaces/ws-1/agent/instructions': null
		});
		vi.stubGlobal('fetch', fetchMock);
		const vm = createAgentPersona('ws-1');
		vm.workspaceText = 'Be terse';
		vm.personalText = 'ignored for this scope';

		await vm.saveInstructions('workspace');

		const [, init] = (fetchMock as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
		expect(JSON.parse(String(init?.body))).toEqual({ scope: 'workspace', text: 'Be terse' });
		expect(vm.error).toBeNull();
		expect(vm.busy).toBe(false);
	});

	it('saveInstructions PUTs the personal text for the personal scope', async () => {
		const fetchMock = routedFetch({
			'PUT /api/v1/workspaces/ws-1/agent/instructions': null
		});
		vi.stubGlobal('fetch', fetchMock);
		const vm = createAgentPersona('ws-1');
		vm.personalText = 'Call me Leo';

		await vm.saveInstructions('personal');

		const [, init] = (fetchMock as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
		expect(JSON.parse(String(init?.body))).toEqual({ scope: 'personal', text: 'Call me Leo' });
	});

	it('saveInstructions clears the layer when the text is blank', async () => {
		const fetchMock = routedFetch({
			'DELETE /api/v1/workspaces/ws-1/agent/instructions?scope=personal': null
		});
		vi.stubGlobal('fetch', fetchMock);
		const vm = createAgentPersona('ws-1');
		vm.personalText = '   ';

		await vm.saveInstructions('personal');

		const [url, init] = (fetchMock as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
		expect(String(url)).toBe('/api/v1/workspaces/ws-1/agent/instructions?scope=personal');
		expect(init?.method).toBe('DELETE');
		expect(vm.error).toBeNull();
	});

	it('saveInstructions surfaces a failure and resets busy', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async () => ({
				ok: false,
				status: 403,
				json: async () => ({ detail: 'members only' })
			})) as unknown as typeof fetch
		);
		const vm = createAgentPersona('ws-1');
		vm.workspaceText = 'Be terse';

		await vm.saveInstructions('workspace');

		expect(vm.error).toMatch(/403/);
		expect(vm.busy).toBe(false);
	});

	it('saveInstructions clears a stale error before retrying', async () => {
		let failNext = true;
		vi.stubGlobal(
			'fetch',
			vi.fn(async () => {
				if (failNext) {
					failNext = false;
					return { ok: false, status: 500, json: async () => ({ detail: 'boom' }) };
				}
				return { ok: true, status: 200, json: async () => null };
			}) as unknown as typeof fetch
		);
		const vm = createAgentPersona('ws-1');
		vm.workspaceText = 'Be terse';

		await vm.saveInstructions('workspace');
		expect(vm.error).toMatch(/500/);

		await vm.saveInstructions('workspace');
		expect(vm.error).toBeNull();
	});

	it('addMemory prepends the trimmed memory and reports success', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/workspaces/ws-1/agent/instructions': { workspace: null, personal: null },
				'GET /api/v1/workspaces/ws-1/agent/memories': [MEMORY('m-old', 'existing')],
				'POST /api/v1/workspaces/ws-1/agent/memories': MEMORY('m-new', 'Prefers dark mode')
			})
		);
		const vm = createAgentPersona('ws-1');
		await vm.load();

		expect(await vm.addMemory('  Prefers dark mode  ')).toBe(true);

		expect(vm.memories.map((m) => m.id)).toEqual(['m-new', 'm-old']);
		const fetchMock = fetch as unknown as ReturnType<typeof vi.fn>;
		const postCall = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST');
		expect(JSON.parse(String(postCall?.[1]?.body))).toEqual({ text: 'Prefers dark mode' });
		expect(vm.busy).toBe(false);
	});

	it('addMemory rejects blank text without calling the API', async () => {
		const fetchMock = vi.fn() as unknown as typeof fetch;
		vi.stubGlobal('fetch', fetchMock);
		const vm = createAgentPersona('ws-1');

		expect(await vm.addMemory('   ')).toBe(false);

		expect(fetchMock).not.toHaveBeenCalled();
		expect(vm.error).toBeNull();
	});

	it('addMemory reports a failure without mutating the list', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async () => ({
				ok: false,
				status: 422,
				json: async () => ({ detail: 'too long' })
			})) as unknown as typeof fetch
		);
		const vm = createAgentPersona('ws-1');

		expect(await vm.addMemory('a memory')).toBe(false);

		expect(vm.memories).toEqual([]);
		expect(vm.error).toMatch(/422/);
		expect(vm.busy).toBe(false);
	});

	it('removeMemory deletes and drops only the matching memory', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/workspaces/ws-1/agent/instructions': { workspace: null, personal: null },
				'GET /api/v1/workspaces/ws-1/agent/memories': [
					MEMORY('m-1', 'keep'),
					MEMORY('m-2', 'drop')
				],
				'DELETE /api/v1/workspaces/ws-1/agent/memories/m-2': null
			})
		);
		const vm = createAgentPersona('ws-1');
		await vm.load();

		await vm.removeMemory('m-2');

		expect(vm.memories.map((m) => m.id)).toEqual(['m-1']);
	});

	it('removeMemory keeps the memory when the delete fails', async () => {
		let deleted = false;
		vi.stubGlobal(
			'fetch',
			vi.fn(async (_url: string, init?: RequestInit) => {
				if (init?.method === 'DELETE') {
					deleted = true;
					return { ok: false, status: 403, json: async () => ({ detail: 'not yours' }) };
				}
				return {
					ok: true,
					status: 200,
					json: async () =>
						String(_url).endsWith('/memories')
							? [MEMORY('m-1', 'keep')]
							: { workspace: null, personal: null }
				};
			}) as unknown as typeof fetch
		);
		const vm = createAgentPersona('ws-1');
		await vm.load();

		await vm.removeMemory('m-1');

		expect(deleted).toBe(true);
		expect(vm.memories.map((m) => m.id)).toEqual(['m-1']);
		expect(vm.error).toMatch(/403/);
	});

	it('text setters update the exposed getters', () => {
		const vm = createAgentPersona('ws-1');

		vm.workspaceText = 'shared rules';
		vm.personalText = 'my rules';

		expect(vm.workspaceText).toBe('shared rules');
		expect(vm.personalText).toBe('my rules');
	});
});
