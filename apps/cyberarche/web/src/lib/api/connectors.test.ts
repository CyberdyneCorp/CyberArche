import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
	listConnectors,
	listExternalTools,
	registerConnector,
	removeConnector,
	setConnectorEnabled
} from './connectors';

const CONNECTOR = {
	id: 'conn-1',
	name: 'GitHub',
	slug: 'github',
	endpoint: 'https://mcp.example.com',
	enabled: true,
	created_by: 'alice',
	created_at: '2026-01-01T00:00:00Z'
};

/** Captures every request and answers with a fixed body/status. */
function capturingFetch(body: unknown, status = 200) {
	return vi.fn(async () => ({
		ok: status < 400,
		status,
		json: async () => body
	})) as unknown as typeof fetch;
}

function lastRequest(mock: typeof fetch) {
	const calls = (mock as unknown as ReturnType<typeof vi.fn>).mock.calls;
	const [url, init] = calls[calls.length - 1] as [string, RequestInit | undefined];
	return { url, init };
}

describe('connectors API client', () => {
	beforeEach(() => vi.restoreAllMocks());

	it('listConnectors GETs the workspace connectors collection', async () => {
		const fetchMock = capturingFetch([CONNECTOR]);
		vi.stubGlobal('fetch', fetchMock);

		const result = await listConnectors('ws-1');

		const { url, init } = lastRequest(fetchMock);
		expect(url).toBe('/api/v1/workspaces/ws-1/connectors');
		expect(init?.method).toBeUndefined(); // GET
		expect(result).toEqual([CONNECTOR]);
	});

	it('registerConnector POSTs name, endpoint and credentials', async () => {
		const fetchMock = capturingFetch(CONNECTOR);
		vi.stubGlobal('fetch', fetchMock);

		const result = await registerConnector('ws-1', 'GitHub', 'https://mcp.example.com', 'tok');

		const { url, init } = lastRequest(fetchMock);
		expect(url).toBe('/api/v1/workspaces/ws-1/connectors');
		expect(init?.method).toBe('POST');
		expect(JSON.parse(String(init?.body))).toEqual({
			name: 'GitHub',
			endpoint: 'https://mcp.example.com',
			credentials: 'tok'
		});
		expect(result).toEqual(CONNECTOR);
	});

	it('registerConnector defaults credentials to an empty string', async () => {
		const fetchMock = capturingFetch(CONNECTOR);
		vi.stubGlobal('fetch', fetchMock);

		await registerConnector('ws-1', 'GitHub', 'https://mcp.example.com');

		const { init } = lastRequest(fetchMock);
		expect(JSON.parse(String(init?.body)).credentials).toBe('');
	});

	it('setConnectorEnabled PATCHes the enabled flag', async () => {
		const fetchMock = capturingFetch({ ...CONNECTOR, enabled: false });
		vi.stubGlobal('fetch', fetchMock);

		const result = await setConnectorEnabled('ws-1', 'conn-1', false);

		const { url, init } = lastRequest(fetchMock);
		expect(url).toBe('/api/v1/workspaces/ws-1/connectors/conn-1');
		expect(init?.method).toBe('PATCH');
		expect(JSON.parse(String(init?.body))).toEqual({ enabled: false });
		expect(result.enabled).toBe(false);
	});

	it('removeConnector DELETEs the connector', async () => {
		const fetchMock = capturingFetch(undefined, 204);
		vi.stubGlobal('fetch', fetchMock);

		await expect(removeConnector('ws-1', 'conn-1')).resolves.toBeUndefined();

		const { url, init } = lastRequest(fetchMock);
		expect(url).toBe('/api/v1/workspaces/ws-1/connectors/conn-1');
		expect(init?.method).toBe('DELETE');
	});

	it('listExternalTools GETs the namespaced tools list', async () => {
		const tools = [{ name: 'github__create_issue', description: 'Create an issue' }];
		const fetchMock = capturingFetch(tools);
		vi.stubGlobal('fetch', fetchMock);

		const result = await listExternalTools('ws-1');

		const { url, init } = lastRequest(fetchMock);
		expect(url).toBe('/api/v1/workspaces/ws-1/connectors/tools');
		expect(init?.method).toBeUndefined(); // GET
		expect(result).toEqual(tools);
	});

	it('propagates ApiError details on failure', async () => {
		vi.stubGlobal('fetch', capturingFetch({ detail: 'handshake failed' }, 502));

		await expect(listConnectors('ws-1')).rejects.toThrow('502: handshake failed');
	});
});
