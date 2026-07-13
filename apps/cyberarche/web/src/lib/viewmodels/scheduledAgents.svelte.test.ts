import { beforeEach, describe, expect, it, vi } from 'vitest';

import { createScheduledAgents } from './scheduledAgents.svelte';

const TASK = (id: string, extra: Record<string, unknown> = {}) => ({
	id,
	name: `Task ${id}`,
	instruction: 'Do the thing',
	schedule_cron: '0 9 * * *',
	document_id: null,
	enabled: true,
	next_run_at: null,
	owner_id: 'alice',
	max_tool_rounds: 10,
	max_wall_seconds: 300,
	max_actions: 20,
	...extra
});

const RUN = (id: string) => ({
	id,
	trigger: 'schedule',
	outcome: 'success',
	document_id: null,
	detail: 'ok',
	started_at: '2026-07-12T09:00:00Z',
	finished_at: '2026-07-12T09:00:05Z'
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

describe('scheduled agents ViewModel', () => {
	beforeEach(() => vi.restoreAllMocks());

	it('starts empty and idle', () => {
		const vm = createScheduledAgents('ws-1');

		expect(vm.tasks).toEqual([]);
		expect(vm.runs).toEqual({});
		expect(vm.error).toBeNull();
		expect(vm.busy).toBe(false);
	});

	it('load fetches the workspace tasks', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({ 'GET /api/v1/workspaces/ws-1/agent/tasks': [TASK('t-1'), TASK('t-2')] })
		);
		const vm = createScheduledAgents('ws-1');

		await vm.load();

		expect(vm.tasks.map((t) => t.id)).toEqual(['t-1', 't-2']);
		expect(vm.error).toBeNull();
	});

	it('load surfaces an ApiError as "status: message"', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async () => ({
				ok: false,
				status: 403,
				json: async () => ({ detail: 'forbidden' })
			})) as unknown as typeof fetch
		);
		const vm = createScheduledAgents('ws-1');

		await vm.load();

		expect(vm.tasks).toEqual([]);
		expect(vm.error).toBe('403: 403: forbidden');
	});

	it('load stringifies a non-ApiError failure', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async () => {
				throw new Error('network down');
			}) as unknown as typeof fetch
		);
		const vm = createScheduledAgents('ws-1');

		await vm.load();

		expect(vm.error).toBe('Error: network down');
	});

	it('create prepends the new task and defaults document_id to null', async () => {
		const bodies: unknown[] = [];
		vi.stubGlobal(
			'fetch',
			vi.fn(async (url: string, init?: RequestInit) => {
				const key = `${init?.method ?? 'GET'} ${url}`;
				if (key === 'GET /api/v1/workspaces/ws-1/agent/tasks') {
					return { ok: true, status: 200, json: async () => [TASK('t-old')] };
				}
				if (key === 'POST /api/v1/workspaces/ws-1/agent/tasks') {
					bodies.push(JSON.parse(String(init?.body)));
					return { ok: true, status: 200, json: async () => TASK('t-new') };
				}
				throw new Error(`unrouted: ${key}`);
			}) as unknown as typeof fetch
		);
		const vm = createScheduledAgents('ws-1');
		await vm.load();

		const ok = await vm.create('Digest', 'Summarise', '0 9 * * *');

		expect(ok).toBe(true);
		expect(vm.tasks.map((t) => t.id)).toEqual(['t-new', 't-old']);
		expect(bodies).toEqual([
			{ name: 'Digest', instruction: 'Summarise', schedule_cron: '0 9 * * *', document_id: null }
		]);
		expect(vm.busy).toBe(false);
		expect(vm.error).toBeNull();
	});

	it('create passes the target document id through', async () => {
		const bodies: unknown[] = [];
		vi.stubGlobal(
			'fetch',
			vi.fn(async (_url: string, init?: RequestInit) => {
				bodies.push(JSON.parse(String(init?.body)));
				return { ok: true, status: 200, json: async () => TASK('t-1', { document_id: 'doc-7' }) };
			}) as unknown as typeof fetch
		);
		const vm = createScheduledAgents('ws-1');

		expect(await vm.create('Digest', 'Summarise', '0 9 * * *', 'doc-7')).toBe(true);
		expect(bodies[0]).toMatchObject({ document_id: 'doc-7' });
	});

	it('create rejects blank name, instruction, or cron without calling the API', async () => {
		const fetchSpy = vi.fn() as unknown as typeof fetch;
		vi.stubGlobal('fetch', fetchSpy);
		const vm = createScheduledAgents('ws-1');

		expect(await vm.create('  ', 'Summarise', '0 9 * * *')).toBe(false);
		expect(await vm.create('Digest', '  ', '0 9 * * *')).toBe(false);
		expect(await vm.create('Digest', 'Summarise', '  ')).toBe(false);
		expect(fetchSpy).not.toHaveBeenCalled();
		expect(vm.busy).toBe(false);
	});

	it('create surfaces a failure, returns false, and clears busy', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async () => ({
				ok: false,
				status: 422,
				json: async () => ({ detail: 'bad cron' })
			})) as unknown as typeof fetch
		);
		const vm = createScheduledAgents('ws-1');

		expect(await vm.create('Digest', 'Summarise', 'nonsense')).toBe(false);
		expect(vm.tasks).toEqual([]);
		expect(vm.error).toBe('422: 422: bad cron');
		expect(vm.busy).toBe(false);
	});

	it('create clears a previous error before retrying', async () => {
		let failNext = true;
		vi.stubGlobal(
			'fetch',
			vi.fn(async () => {
				if (failNext) {
					failNext = false;
					return { ok: false, status: 500, json: async () => ({ detail: 'boom' }) };
				}
				return { ok: true, status: 200, json: async () => TASK('t-1') };
			}) as unknown as typeof fetch
		);
		const vm = createScheduledAgents('ws-1');

		expect(await vm.create('Digest', 'Summarise', '0 9 * * *')).toBe(false);
		expect(vm.error).toMatch(/500/);

		expect(await vm.create('Digest', 'Summarise', '0 9 * * *')).toBe(true);
		expect(vm.error).toBeNull();
	});

	it('toggle flips only the targeted task via the server response', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/workspaces/ws-1/agent/tasks': [TASK('t-1'), TASK('t-2')],
				'PATCH /api/v1/workspaces/ws-1/agent/tasks/t-1': TASK('t-1', { enabled: false })
			})
		);
		const vm = createScheduledAgents('ws-1');
		await vm.load();

		await vm.toggle(vm.tasks[0]);

		expect(vm.tasks.find((t) => t.id === 't-1')?.enabled).toBe(false);
		expect(vm.tasks.find((t) => t.id === 't-2')?.enabled).toBe(true);
	});

	it('toggle sends the inverted enabled flag', async () => {
		const bodies: unknown[] = [];
		vi.stubGlobal(
			'fetch',
			vi.fn(async (_url: string, init?: RequestInit) => {
				if (init?.method === 'PATCH') bodies.push(JSON.parse(String(init.body)));
				return { ok: true, status: 200, json: async () => TASK('t-1', { enabled: true }) };
			}) as unknown as typeof fetch
		);
		const vm = createScheduledAgents('ws-1');

		await vm.toggle(TASK('t-1', { enabled: false }) as (typeof vm.tasks)[number]);

		expect(bodies).toEqual([{ enabled: true }]);
	});

	it('toggle surfaces a failure and leaves the list unchanged', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async (_url: string, init?: RequestInit) => {
				if (init?.method === 'PATCH') {
					return { ok: false, status: 404, json: async () => ({ detail: 'gone' }) };
				}
				return { ok: true, status: 200, json: async () => [TASK('t-1')] };
			}) as unknown as typeof fetch
		);
		const vm = createScheduledAgents('ws-1');
		await vm.load();

		await vm.toggle(vm.tasks[0]);

		expect(vm.tasks[0].enabled).toBe(true);
		expect(vm.error).toBe('404: 404: gone');
	});

	it('remove deletes the task from the list', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async (url: string, init?: RequestInit) => {
				if (init?.method === 'DELETE') {
					expect(url).toBe('/api/v1/workspaces/ws-1/agent/tasks/t-1');
					return { ok: true, status: 204, json: async () => null };
				}
				return { ok: true, status: 200, json: async () => [TASK('t-1'), TASK('t-2')] };
			}) as unknown as typeof fetch
		);
		const vm = createScheduledAgents('ws-1');
		await vm.load();

		await vm.remove('t-1');

		expect(vm.tasks.map((t) => t.id)).toEqual(['t-2']);
		expect(vm.error).toBeNull();
	});

	it('remove surfaces a failure and keeps the task', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async (_url: string, init?: RequestInit) => {
				if (init?.method === 'DELETE') {
					return { ok: false, status: 403, json: async () => ({ detail: 'not owner' }) };
				}
				return { ok: true, status: 200, json: async () => [TASK('t-1')] };
			}) as unknown as typeof fetch
		);
		const vm = createScheduledAgents('ws-1');
		await vm.load();

		await vm.remove('t-1');

		expect(vm.tasks.map((t) => t.id)).toEqual(['t-1']);
		expect(vm.error).toBe('403: 403: not owner');
	});

	it('loadRuns stores run history per task without clobbering others', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/workspaces/ws-1/agent/tasks/t-1/runs': [RUN('r-1')],
				'GET /api/v1/workspaces/ws-1/agent/tasks/t-2/runs': [RUN('r-2'), RUN('r-3')]
			})
		);
		const vm = createScheduledAgents('ws-1');

		await vm.loadRuns('t-1');
		await vm.loadRuns('t-2');

		expect(vm.runs['t-1'].map((r) => r.id)).toEqual(['r-1']);
		expect(vm.runs['t-2'].map((r) => r.id)).toEqual(['r-2', 'r-3']);
	});

	it('loadRuns surfaces a failure', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async () => ({
				ok: false,
				status: 500,
				json: async () => ({ detail: 'oops' })
			})) as unknown as typeof fetch
		);
		const vm = createScheduledAgents('ws-1');

		await vm.loadRuns('t-1');

		expect(vm.runs).toEqual({});
		expect(vm.error).toBe('500: 500: oops');
	});
});
