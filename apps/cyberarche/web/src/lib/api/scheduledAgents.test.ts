import { beforeEach, describe, expect, it, vi } from 'vitest';

import { createTask, deleteTask, listTaskRuns, listTasks, setTaskEnabled } from './scheduledAgents';

const TASK = {
	id: 'task-1',
	name: 'Digest',
	instruction: 'Summarise the inbox',
	schedule_cron: '0 9 * * *',
	document_id: null,
	enabled: true,
	next_run_at: '2026-07-13T09:00:00Z',
	owner_id: 'alice',
	max_tool_rounds: 10,
	max_wall_seconds: 300,
	max_actions: 20
};

/** Records every call so URL, method, and body shapes can be asserted. */
function recordingFetch(body: unknown, status = 200) {
	const calls: Array<{ url: string; method: string; body: unknown }> = [];
	const fn = vi.fn(async (url: string, init?: RequestInit) => {
		calls.push({
			url,
			method: init?.method ?? 'GET',
			body: init?.body ? JSON.parse(String(init.body)) : undefined
		});
		return { ok: true, status, json: async () => body };
	}) as unknown as typeof fetch;
	vi.stubGlobal('fetch', fn);
	return calls;
}

describe('scheduled agents API client', () => {
	beforeEach(() => vi.restoreAllMocks());

	it('listTasks GETs the workspace tasks collection', async () => {
		const calls = recordingFetch([TASK]);

		const tasks = await listTasks('ws-1');

		expect(calls).toEqual([
			{ url: '/api/v1/workspaces/ws-1/agent/tasks', method: 'GET', body: undefined }
		]);
		expect(tasks).toEqual([TASK]);
	});

	it('createTask POSTs the task and defaults document_id to null', async () => {
		const calls = recordingFetch(TASK);

		const created = await createTask('ws-1', {
			name: 'Digest',
			instruction: 'Summarise the inbox',
			schedule_cron: '0 9 * * *'
		});

		expect(calls).toEqual([
			{
				url: '/api/v1/workspaces/ws-1/agent/tasks',
				method: 'POST',
				body: {
					name: 'Digest',
					instruction: 'Summarise the inbox',
					schedule_cron: '0 9 * * *',
					document_id: null
				}
			}
		]);
		expect(created).toEqual(TASK);
	});

	it('createTask sends an explicit document_id when provided', async () => {
		const calls = recordingFetch({ ...TASK, document_id: 'doc-7' });

		await createTask('ws-1', {
			name: 'Digest',
			instruction: 'Summarise the inbox',
			schedule_cron: '0 9 * * *',
			document_id: 'doc-7'
		});

		expect(calls[0].body).toMatchObject({ document_id: 'doc-7' });
	});

	it('setTaskEnabled PATCHes the enabled flag', async () => {
		const calls = recordingFetch({ ...TASK, enabled: false });

		const updated = await setTaskEnabled('ws-1', 'task-1', false);

		expect(calls).toEqual([
			{
				url: '/api/v1/workspaces/ws-1/agent/tasks/task-1',
				method: 'PATCH',
				body: { enabled: false }
			}
		]);
		expect(updated.enabled).toBe(false);
	});

	it('deleteTask DELETEs the task resource', async () => {
		const calls = recordingFetch(undefined, 204);

		await deleteTask('ws-1', 'task-1');

		expect(calls).toEqual([
			{ url: '/api/v1/workspaces/ws-1/agent/tasks/task-1', method: 'DELETE', body: undefined }
		]);
	});

	it('listTaskRuns GETs the run history for a task', async () => {
		const run = {
			id: 'run-1',
			trigger: 'schedule',
			outcome: 'success',
			document_id: null,
			detail: 'ok',
			started_at: '2026-07-12T09:00:00Z',
			finished_at: '2026-07-12T09:00:05Z'
		};
		const calls = recordingFetch([run]);

		const runs = await listTaskRuns('ws-1', 'task-1');

		expect(calls).toEqual([
			{ url: '/api/v1/workspaces/ws-1/agent/tasks/task-1/runs', method: 'GET', body: undefined }
		]);
		expect(runs).toEqual([run]);
	});
});
