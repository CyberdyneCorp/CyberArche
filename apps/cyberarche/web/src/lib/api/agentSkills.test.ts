import { beforeEach, describe, expect, it, vi } from 'vitest';

import { deleteSkill, instantiateSkill, listSkills, saveSkill, updateSkill } from './agentSkills';

const SKILL = {
	id: 'sk-1',
	name: 'Summarize',
	description: 'Summarize a doc',
	instruction: 'Summarize {{doc}}',
	variables: ['doc'],
	created_by: 'alice',
	created_at: '2026-01-01T00:00:00Z'
};

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

describe('agent skills API client', () => {
	beforeEach(() => vi.restoreAllMocks());

	it('listSkills GETs the workspace skills collection', async () => {
		const { fn, calls } = capturingFetch([SKILL]);
		vi.stubGlobal('fetch', fn);

		const skills = await listSkills('ws-1');

		expect(calls).toEqual([
			{ url: '/api/v1/workspaces/ws-1/agent/skills', method: 'GET', body: undefined }
		]);
		expect(skills).toEqual([SKILL]);
	});

	it('saveSkill POSTs the skill, defaulting description to an empty string', async () => {
		const { fn, calls } = capturingFetch(SKILL);
		vi.stubGlobal('fetch', fn);

		const created = await saveSkill('ws-1', { name: 'Summarize', instruction: 'Summarize {{doc}}' });

		expect(calls).toEqual([
			{
				url: '/api/v1/workspaces/ws-1/agent/skills',
				method: 'POST',
				body: { name: 'Summarize', instruction: 'Summarize {{doc}}', description: '' }
			}
		]);
		expect(created).toEqual(SKILL);
	});

	it('saveSkill keeps an explicit description', async () => {
		const { fn, calls } = capturingFetch(SKILL);
		vi.stubGlobal('fetch', fn);

		await saveSkill('ws-1', { name: 'S', instruction: 'I', description: 'custom' });

		expect(calls[0].body).toEqual({ name: 'S', instruction: 'I', description: 'custom' });
	});

	it('updateSkill PUTs to the skill URL, defaulting description', async () => {
		const { fn, calls } = capturingFetch(SKILL);
		vi.stubGlobal('fetch', fn);

		const updated = await updateSkill('ws-1', 'sk-1', { name: 'S2', instruction: 'I2' });

		expect(calls).toEqual([
			{
				url: '/api/v1/workspaces/ws-1/agent/skills/sk-1',
				method: 'PUT',
				body: { name: 'S2', instruction: 'I2', description: '' }
			}
		]);
		expect(updated).toEqual(SKILL);
	});

	it('updateSkill keeps an explicit description', async () => {
		const { fn, calls } = capturingFetch(SKILL);
		vi.stubGlobal('fetch', fn);

		await updateSkill('ws-1', 'sk-1', { name: 'S2', instruction: 'I2', description: 'kept' });

		expect(calls[0].body).toEqual({ name: 'S2', instruction: 'I2', description: 'kept' });
	});

	it('deleteSkill DELETEs the skill URL', async () => {
		const { fn, calls } = capturingFetch(null);
		vi.stubGlobal('fetch', fn);

		await deleteSkill('ws-1', 'sk-1');

		expect(calls).toEqual([
			{ url: '/api/v1/workspaces/ws-1/agent/skills/sk-1', method: 'DELETE', body: undefined }
		]);
	});

	it('instantiateSkill POSTs the variable values and returns the instruction', async () => {
		const { fn, calls } = capturingFetch({ instruction: 'Summarize the spec' });
		vi.stubGlobal('fetch', fn);

		const result = await instantiateSkill('ws-1', 'sk-1', { doc: 'the spec' });

		expect(calls).toEqual([
			{
				url: '/api/v1/workspaces/ws-1/agent/skills/sk-1/instantiate',
				method: 'POST',
				body: { values: { doc: 'the spec' } }
			}
		]);
		expect(result).toEqual({ instruction: 'Summarize the spec' });
	});
});
