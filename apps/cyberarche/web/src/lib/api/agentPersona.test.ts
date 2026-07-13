import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
	addMemory,
	clearInstructions,
	deleteMemory,
	getInstructions,
	listMemories,
	setInstructions,
	updateMemory
} from './agentPersona';

const MEMORY = {
	id: 'mem-1',
	text: 'Prefers dark mode',
	created_by: 'alice',
	created_at: '2026-01-01T00:00:00Z',
	updated_at: '2026-01-01T00:00:00Z'
};

/** Records every fetch call so each client's URL/method/body can be asserted. */
function recordingFetch(status: number, body: unknown) {
	return vi.fn(async () => ({
		ok: status < 400,
		status,
		json: async () => body
	})) as unknown as typeof fetch;
}

function lastCall(fn: typeof fetch): { url: string; init?: RequestInit } {
	const calls = (fn as unknown as ReturnType<typeof vi.fn>).mock.calls;
	const [url, init] = calls[calls.length - 1];
	return { url: String(url), init };
}

describe('agentPersona API client', () => {
	beforeEach(() => vi.restoreAllMocks());

	it('getInstructions GETs the workspace instructions endpoint', async () => {
		const fetchMock = recordingFetch(200, { workspace: 'Be terse', personal: null });
		vi.stubGlobal('fetch', fetchMock);

		const result = await getInstructions('ws-1');

		const { url, init } = lastCall(fetchMock);
		expect(url).toBe('/api/v1/workspaces/ws-1/agent/instructions');
		expect(init?.method).toBeUndefined();
		expect(result).toEqual({ workspace: 'Be terse', personal: null });
	});

	it('setInstructions PUTs scope and text', async () => {
		const fetchMock = recordingFetch(200, null);
		vi.stubGlobal('fetch', fetchMock);

		await setInstructions('ws-1', 'personal', 'Call me Leo');

		const { url, init } = lastCall(fetchMock);
		expect(url).toBe('/api/v1/workspaces/ws-1/agent/instructions');
		expect(init?.method).toBe('PUT');
		expect(JSON.parse(String(init?.body))).toEqual({ scope: 'personal', text: 'Call me Leo' });
	});

	it('clearInstructions DELETEs with the scope as a query param', async () => {
		const fetchMock = recordingFetch(204, undefined);
		vi.stubGlobal('fetch', fetchMock);

		await clearInstructions('ws-1', 'workspace');

		const { url, init } = lastCall(fetchMock);
		expect(url).toBe('/api/v1/workspaces/ws-1/agent/instructions?scope=workspace');
		expect(init?.method).toBe('DELETE');
	});

	it('listMemories GETs the memories collection', async () => {
		const fetchMock = recordingFetch(200, [MEMORY]);
		vi.stubGlobal('fetch', fetchMock);

		const result = await listMemories('ws-1');

		const { url, init } = lastCall(fetchMock);
		expect(url).toBe('/api/v1/workspaces/ws-1/agent/memories');
		expect(init?.method).toBeUndefined();
		expect(result).toEqual([MEMORY]);
	});

	it('addMemory POSTs the text and returns the created memory', async () => {
		const fetchMock = recordingFetch(200, MEMORY);
		vi.stubGlobal('fetch', fetchMock);

		const result = await addMemory('ws-1', 'Prefers dark mode');

		const { url, init } = lastCall(fetchMock);
		expect(url).toBe('/api/v1/workspaces/ws-1/agent/memories');
		expect(init?.method).toBe('POST');
		expect(JSON.parse(String(init?.body))).toEqual({ text: 'Prefers dark mode' });
		expect(result).toEqual(MEMORY);
	});

	it('updateMemory PATCHes the memory by id', async () => {
		const updated = { ...MEMORY, text: 'Prefers light mode' };
		const fetchMock = recordingFetch(200, updated);
		vi.stubGlobal('fetch', fetchMock);

		const result = await updateMemory('ws-1', 'mem-1', 'Prefers light mode');

		const { url, init } = lastCall(fetchMock);
		expect(url).toBe('/api/v1/workspaces/ws-1/agent/memories/mem-1');
		expect(init?.method).toBe('PATCH');
		expect(JSON.parse(String(init?.body))).toEqual({ text: 'Prefers light mode' });
		expect(result).toEqual(updated);
	});

	it('deleteMemory DELETEs the memory by id', async () => {
		const fetchMock = recordingFetch(204, undefined);
		vi.stubGlobal('fetch', fetchMock);

		await deleteMemory('ws-1', 'mem-1');

		const { url, init } = lastCall(fetchMock);
		expect(url).toBe('/api/v1/workspaces/ws-1/agent/memories/mem-1');
		expect(init?.method).toBe('DELETE');
	});
});
