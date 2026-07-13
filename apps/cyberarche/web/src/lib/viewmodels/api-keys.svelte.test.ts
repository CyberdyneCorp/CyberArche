import { beforeEach, describe, expect, it, vi } from 'vitest';

import { createApiKeys } from './api-keys.svelte';

const KEY = (id: string, overrides: Record<string, unknown> = {}) => ({
	id,
	name: `Key ${id}`,
	prefix: `ca_${id}`,
	created_at: '2026-01-01T00:00:00Z',
	expires_at: null,
	revoked: false,
	last_used_at: null,
	...overrides
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

function failingFetch(status: number, detail: string) {
	return vi.fn(async () => ({
		ok: false,
		status,
		json: async () => ({ detail })
	})) as unknown as typeof fetch;
}

describe('api-keys ViewModel', () => {
	beforeEach(() => vi.restoreAllMocks());

	it('load fetches the key list', async () => {
		vi.stubGlobal('fetch', routedFetch({ 'GET /api/v1/api-keys': [KEY('k-1'), KEY('k-2')] }));
		const vm = createApiKeys();

		await vm.load();

		expect(vm.items.map((k) => k.id)).toEqual(['k-1', 'k-2']);
	});

	it('create exposes the secret once and appends the key', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/api-keys': [KEY('k-1')],
				'POST /api/v1/api-keys': { ...KEY('k-2'), secret: 'ca_k-2.s3cr3t' }
			})
		);
		const vm = createApiKeys();
		await vm.load();

		await vm.create('Key k-2');

		expect(vm.justCreated?.secret).toBe('ca_k-2.s3cr3t');
		expect(vm.items.map((k) => k.id)).toEqual(['k-1', 'k-2']);
		expect(vm.error).toBeNull();

		vm.dismissSecret();
		expect(vm.justCreated).toBeNull();
	});

	it('surfaces a create failure without adding a key', async () => {
		vi.stubGlobal('fetch', failingFetch(403, 'quota exceeded'));
		const vm = createApiKeys();

		await vm.create('Denied');

		expect(vm.items).toHaveLength(0);
		expect(vm.justCreated).toBeNull();
		expect(vm.error).toBe('403: quota exceeded');
	});

	it('a successful create clears a previous error', async () => {
		vi.stubGlobal('fetch', failingFetch(403, 'nope'));
		const vm = createApiKeys();
		await vm.create('Denied');
		expect(vm.error).toBe('403: nope');

		vi.stubGlobal(
			'fetch',
			routedFetch({ 'POST /api/v1/api-keys': { ...KEY('k-1'), secret: 's' } })
		);
		await vm.create('Key k-1');

		expect(vm.error).toBeNull();
		expect(vm.items.map((k) => k.id)).toEqual(['k-1']);
	});

	it('revoke replaces only the matching key', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/api-keys': [KEY('k-1'), KEY('k-2')],
				'DELETE /api/v1/api-keys/k-1': KEY('k-1', { revoked: true })
			})
		);
		const vm = createApiKeys();
		await vm.load();

		await vm.revoke('k-1');

		expect(vm.items.find((k) => k.id === 'k-1')?.revoked).toBe(true);
		expect(vm.items.find((k) => k.id === 'k-2')?.revoked).toBe(false);
		expect(vm.error).toBeNull();
	});

	it('surfaces a revoke failure and keeps the list intact', async () => {
		vi.stubGlobal('fetch', routedFetch({ 'GET /api/v1/api-keys': [KEY('k-1')] }));
		const vm = createApiKeys();
		await vm.load();

		vi.stubGlobal('fetch', failingFetch(404, 'not found'));
		await vm.revoke('k-1');

		expect(vm.error).toBe('404: not found');
		expect(vm.items.find((k) => k.id === 'k-1')?.revoked).toBe(false);
	});
});
