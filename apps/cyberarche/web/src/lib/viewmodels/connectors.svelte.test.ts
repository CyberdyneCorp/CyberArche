import { beforeEach, describe, expect, it, vi } from 'vitest';

import { createConnectors } from './connectors.svelte';

const CONNECTOR = (id: string, slug: string, enabled = true) => ({
	id,
	name: slug,
	slug,
	endpoint: `https://${slug}.example.com/mcp`,
	enabled,
	created_by: 'alice',
	created_at: '2026-01-01T00:00:00Z'
});

const TOOL = (name: string) => ({ name, description: `does ${name}` });

/** Routes fetch by URL+method so the VM's real request shapes are exercised. */
function routedFetch(routes: Record<string, unknown>) {
	return vi.fn(async (url: string, init?: RequestInit) => {
		const key = `${init?.method ?? 'GET'} ${url}`;
		const body = routes[key];
		if (body === undefined) throw new Error(`unrouted: ${key}`);
		return { ok: true, status: 200, json: async () => body };
	}) as unknown as typeof fetch;
}

describe('connectors ViewModel', () => {
	beforeEach(() => vi.restoreAllMocks());

	it('load fetches connectors and their namespaced tools', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/workspaces/ws-1/connectors': [CONNECTOR('c-1', 'github')],
				'GET /api/v1/workspaces/ws-1/connectors/tools': [TOOL('github__create_issue')]
			})
		);
		const vm = createConnectors('ws-1');
		await vm.load();

		expect(vm.items.map((c) => c.id)).toEqual(['c-1']);
		expect(vm.tools.map((t) => t.name)).toEqual(['github__create_issue']);
		expect(vm.error).toBeNull();
		expect(vm.busy).toBe(false);
	});

	it('a tools fetch failure leaves an empty tool list, not an error', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async (url: string) => {
				if (url.endsWith('/tools')) {
					return { ok: false, status: 500, json: async () => ({ detail: 'boom' }) };
				}
				return { ok: true, status: 200, json: async () => [CONNECTOR('c-1', 'github')] };
			}) as unknown as typeof fetch
		);
		const vm = createConnectors('ws-1');
		await vm.load();

		expect(vm.items).toHaveLength(1);
		expect(vm.tools).toEqual([]);
		expect(vm.error).toBeNull();
	});

	it('toolsOf filters tools by the connector slug namespace', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/workspaces/ws-1/connectors': [
					CONNECTOR('c-1', 'github'),
					CONNECTOR('c-2', 'linear')
				],
				'GET /api/v1/workspaces/ws-1/connectors/tools': [
					TOOL('github__create_issue'),
					TOOL('github__list_prs'),
					TOOL('linear__create_ticket')
				]
			})
		);
		const vm = createConnectors('ws-1');
		await vm.load();

		expect(vm.toolsOf(vm.items[0]).map((t) => t.name)).toEqual([
			'github__create_issue',
			'github__list_prs'
		]);
		expect(vm.toolsOf(vm.items[1]).map((t) => t.name)).toEqual(['linear__create_ticket']);
	});

	it('register appends the connector, refreshes tools and reports success', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/workspaces/ws-1/connectors': [],
				'GET /api/v1/workspaces/ws-1/connectors/tools': [TOOL('github__create_issue')],
				'POST /api/v1/workspaces/ws-1/connectors': CONNECTOR('c-new', 'github')
			})
		);
		const vm = createConnectors('ws-1');
		await vm.load();

		expect(await vm.register('GitHub', 'https://github.example.com/mcp', 'tok')).toBe(true);

		expect(vm.items.map((c) => c.id)).toEqual(['c-new']);
		expect(vm.tools.map((t) => t.name)).toEqual(['github__create_issue']);
		expect(vm.error).toBeNull();
		expect(vm.busy).toBe(false);
	});

	it('register sends default empty credentials when omitted', async () => {
		const bodies: Array<Record<string, unknown>> = [];
		vi.stubGlobal(
			'fetch',
			vi.fn(async (_url: string, init?: RequestInit) => {
				if (init?.method === 'POST') bodies.push(JSON.parse(String(init.body)));
				return { ok: true, status: 200, json: async () => CONNECTOR('c-new', 'github') };
			}) as unknown as typeof fetch
		);
		const vm = createConnectors('ws-1');

		expect(await vm.register('GitHub', 'https://github.example.com/mcp')).toBe(true);

		expect(bodies).toEqual([
			{ name: 'GitHub', endpoint: 'https://github.example.com/mcp', credentials: '' }
		]);
	});

	it('a failed handshake surfaces the error, adds nothing and clears busy', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async (url: string, init?: RequestInit) => {
				if (init?.method === 'POST') {
					return { ok: false, status: 502, json: async () => ({ detail: 'unreachable' }) };
				}
				return { ok: true, status: 200, json: async () => [] };
			}) as unknown as typeof fetch
		);
		const vm = createConnectors('ws-1');
		await vm.load();

		expect(await vm.register('Bad', 'https://down.example.com')).toBe(false);

		expect(vm.items).toHaveLength(0);
		expect(vm.error).toBe('502: unreachable');
		expect(vm.busy).toBe(false);
	});

	it('busy is true while a registration is in flight', async () => {
		let release!: () => void;
		const gate = new Promise<void>((resolve) => (release = resolve));
		vi.stubGlobal(
			'fetch',
			vi.fn(async (_url: string, init?: RequestInit) => {
				if (init?.method === 'POST') await gate;
				return {
					ok: true,
					status: 200,
					json: async () => (init?.method === 'POST' ? CONNECTOR('c-new', 'github') : [])
				};
			}) as unknown as typeof fetch
		);
		const vm = createConnectors('ws-1');

		const pending = vm.register('GitHub', 'https://github.example.com/mcp');
		expect(vm.busy).toBe(true);

		release();
		await pending;
		expect(vm.busy).toBe(false);
	});

	it('register clears a previous error on the next attempt', async () => {
		let fail = true;
		vi.stubGlobal(
			'fetch',
			vi.fn(async (_url: string, init?: RequestInit) => {
				if (init?.method === 'POST' && fail) {
					return { ok: false, status: 502, json: async () => ({ detail: 'unreachable' }) };
				}
				return {
					ok: true,
					status: 200,
					json: async () => (init?.method === 'POST' ? CONNECTOR('c-new', 'github') : [])
				};
			}) as unknown as typeof fetch
		);
		const vm = createConnectors('ws-1');

		await vm.register('Bad', 'https://down.example.com');
		expect(vm.error).toBe('502: unreachable');

		fail = false;
		expect(await vm.register('GitHub', 'https://github.example.com/mcp')).toBe(true);
		expect(vm.error).toBeNull();
	});

	it('setEnabled swaps in the updated connector and refreshes tools', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/workspaces/ws-1/connectors': [
					CONNECTOR('c-1', 'github'),
					CONNECTOR('c-2', 'linear')
				],
				'GET /api/v1/workspaces/ws-1/connectors/tools': [],
				'PATCH /api/v1/workspaces/ws-1/connectors/c-1': CONNECTOR('c-1', 'github', false)
			})
		);
		const vm = createConnectors('ws-1');
		await vm.load();

		await vm.setEnabled('c-1', false);

		expect(vm.items.find((c) => c.id === 'c-1')?.enabled).toBe(false);
		expect(vm.items.find((c) => c.id === 'c-2')?.enabled).toBe(true); // untouched
		expect(vm.error).toBeNull();
	});

	it('setEnabled failure surfaces the error and leaves items unchanged', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async (_url: string, init?: RequestInit) => {
				if (init?.method === 'PATCH') {
					return { ok: false, status: 403, json: async () => ({ detail: 'forbidden' }) };
				}
				return {
					ok: true,
					status: 200,
					json: async () => (String(_url).endsWith('/tools') ? [] : [CONNECTOR('c-1', 'github')])
				};
			}) as unknown as typeof fetch
		);
		const vm = createConnectors('ws-1');
		await vm.load();

		await vm.setEnabled('c-1', false);

		expect(vm.items[0].enabled).toBe(true);
		expect(vm.error).toBe('403: forbidden');
	});

	it('remove drops the connector and refreshes tools', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/workspaces/ws-1/connectors': [
					CONNECTOR('c-1', 'github'),
					CONNECTOR('c-2', 'linear')
				],
				'GET /api/v1/workspaces/ws-1/connectors/tools': [],
				'DELETE /api/v1/workspaces/ws-1/connectors/c-1': null
			})
		);
		const vm = createConnectors('ws-1');
		await vm.load();

		await vm.remove('c-1');

		expect(vm.items.map((c) => c.id)).toEqual(['c-2']);
		expect(vm.error).toBeNull();
	});

	it('remove failure surfaces the error and keeps the connector', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async (_url: string, init?: RequestInit) => {
				if (init?.method === 'DELETE') {
					return { ok: false, status: 404, json: async () => ({ detail: 'not found' }) };
				}
				return {
					ok: true,
					status: 200,
					json: async () => (String(_url).endsWith('/tools') ? [] : [CONNECTOR('c-1', 'github')])
				};
			}) as unknown as typeof fetch
		);
		const vm = createConnectors('ws-1');
		await vm.load();

		await vm.remove('c-1');

		expect(vm.items.map((c) => c.id)).toEqual(['c-1']);
		expect(vm.error).toBe('404: not found');
	});
});
