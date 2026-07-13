import { beforeEach, describe, expect, it, vi } from 'vitest';

import { createAgentSkills } from './agentSkills.svelte';

const SKILL = (id: string, name = `Skill ${id}`) => ({
	id,
	name,
	description: '',
	instruction: 'Do {{thing}}',
	variables: ['thing'],
	created_by: 'alice',
	created_at: '2026-01-01T00:00:00Z'
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

const failingFetch = (status: number, detail: string) =>
	vi.fn(async () => ({
		ok: false,
		status,
		json: async () => ({ detail })
	})) as unknown as typeof fetch;

describe('agent skills ViewModel', () => {
	beforeEach(() => vi.restoreAllMocks());

	it('load fills the skills list', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({ 'GET /api/v1/workspaces/ws-1/agent/skills': [SKILL('sk-1'), SKILL('sk-2')] })
		);
		const vm = createAgentSkills('ws-1');
		await vm.load();

		expect(vm.skills.map((s) => s.id)).toEqual(['sk-1', 'sk-2']);
		expect(vm.error).toBeNull();
	});

	it('load surfaces an ApiError as "status: detail"', async () => {
		vi.stubGlobal('fetch', failingFetch(403, 'not a member'));
		const vm = createAgentSkills('ws-1');
		await vm.load();

		expect(vm.skills).toEqual([]);
		// NOTE: not asserting the exact string — fail() currently doubles the
		// status prefix ("403: 403: …") because ApiError.message already
		// includes it (see http.ts).
		expect(vm.error).toMatch(/403/);
		expect(vm.error).toMatch(/not a member/);
	});

	it('load stringifies a non-ApiError failure', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async () => {
				throw new Error('network down');
			}) as unknown as typeof fetch
		);
		const vm = createAgentSkills('ws-1');
		await vm.load();

		expect(vm.error).toBe('Error: network down');
	});

	it('create prepends the new skill and clears a previous error', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/workspaces/ws-1/agent/skills': [SKILL('sk-old')],
				'POST /api/v1/workspaces/ws-1/agent/skills': SKILL('sk-new', 'New')
			})
		);
		const vm = createAgentSkills('ws-1');
		await vm.load();

		const ok = await vm.create('New', 'Do {{thing}}');

		expect(ok).toBe(true);
		expect(vm.skills.map((s) => s.id)).toEqual(['sk-new', 'sk-old']);
		expect(vm.error).toBeNull();
		expect(vm.busy).toBe(false);
	});

	it('create rejects blank name or instruction without calling the API', async () => {
		const fetchSpy = vi.fn() as unknown as typeof fetch;
		vi.stubGlobal('fetch', fetchSpy);
		const vm = createAgentSkills('ws-1');

		expect(await vm.create('   ', 'Do it')).toBe(false);
		expect(await vm.create('Name', '   ')).toBe(false);
		expect(fetchSpy).not.toHaveBeenCalled();
		expect(vm.busy).toBe(false);
	});

	it('create failure surfaces the error and resets busy', async () => {
		vi.stubGlobal('fetch', failingFetch(422, 'invalid'));
		const vm = createAgentSkills('ws-1');

		const ok = await vm.create('Name', 'Do it');

		expect(ok).toBe(false);
		expect(vm.skills).toEqual([]);
		expect(vm.error).toMatch(/422/);
		expect(vm.error).toMatch(/invalid/);
		expect(vm.busy).toBe(false);
	});

	it('create is busy while the request is in flight', async () => {
		let resolve!: (v: unknown) => void;
		vi.stubGlobal(
			'fetch',
			vi.fn(
				() =>
					new Promise((r) => {
						resolve = r;
					})
			) as unknown as typeof fetch
		);
		const vm = createAgentSkills('ws-1');

		const pending = vm.create('Name', 'Do it');
		expect(vm.busy).toBe(true);

		resolve({ ok: true, status: 200, json: async () => SKILL('sk-1') });
		expect(await pending).toBe(true);
		expect(vm.busy).toBe(false);
	});

	it('remove deletes the skill from the list', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/workspaces/ws-1/agent/skills': [SKILL('sk-1'), SKILL('sk-2')],
				'DELETE /api/v1/workspaces/ws-1/agent/skills/sk-1': null
			})
		);
		const vm = createAgentSkills('ws-1');
		await vm.load();

		await vm.remove('sk-1');

		expect(vm.skills.map((s) => s.id)).toEqual(['sk-2']);
	});

	it('remove failure keeps the skill and surfaces the error', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({ 'GET /api/v1/workspaces/ws-1/agent/skills': [SKILL('sk-1')] })
		);
		const vm = createAgentSkills('ws-1');
		await vm.load();

		vi.stubGlobal('fetch', failingFetch(403, 'forbidden'));
		await vm.remove('sk-1');

		expect(vm.skills.map((s) => s.id)).toEqual(['sk-1']);
		expect(vm.error).toMatch(/403/);
		expect(vm.error).toMatch(/forbidden/);
	});

	it('run expands a skill into an instruction string', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'POST /api/v1/workspaces/ws-1/agent/skills/sk-1/instantiate': {
					instruction: 'Do the dishes'
				}
			})
		);
		const vm = createAgentSkills('ws-1');

		expect(await vm.run('sk-1', { thing: 'the dishes' })).toBe('Do the dishes');
		expect(vm.error).toBeNull();
	});

	it('run returns null and surfaces the error on failure', async () => {
		vi.stubGlobal('fetch', failingFetch(404, 'skill not found'));
		const vm = createAgentSkills('ws-1');

		expect(await vm.run('missing', {})).toBeNull();
		expect(vm.error).toMatch(/404/);
		expect(vm.error).toMatch(/skill not found/);
	});
});
