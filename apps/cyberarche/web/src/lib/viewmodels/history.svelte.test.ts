import { beforeEach, describe, expect, it, vi } from 'vitest';

import { createHistory } from './history.svelte';

const SNAP = (id: string, seq: number, overrides: Record<string, unknown> = {}) => ({
	id,
	document_id: 'd-1',
	seq,
	created_at: '2026-01-01T00:00:00Z',
	restored_from: null,
	created_by: 'alice',
	label: null,
	...overrides
});

/** Routes fetch by method+URL so the VM's real request shapes are exercised. */
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

describe('history ViewModel', () => {
	beforeEach(() => vi.restoreAllMocks());

	it('load lists versions newest-first', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/documents/d-1/snapshots': [SNAP('s-1', 1), SNAP('s-2', 2)]
			})
		);
		const vm = createHistory('d-1');

		await vm.load();

		expect(vm.versions.map((v) => v.id)).toEqual(['s-2', 's-1']);
		expect(vm.error).toBeNull();
	});

	it('diffAgainst current returns block changes and marks the compared version', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/documents/d-1/snapshots/diff?from=s-1': {
					added: [{ id: 'b2', type: 'paragraph', data: { text: 'new' } }],
					removed: [],
					modified: [{ id: 'b1', before: 'old', after: 'edited' }]
				}
			})
		);
		const vm = createHistory('d-1');

		await vm.diffAgainst('s-1');

		expect(vm.comparing).toBe('s-1');
		expect(vm.diff?.added.map((b) => b.id)).toEqual(['b2']);
		expect(vm.diff?.modified).toEqual([{ id: 'b1', before: 'old', after: 'edited' }]);

		vm.closeDiff();
		expect(vm.diff).toBeNull();
		expect(vm.comparing).toBeNull();
	});

	it('diffAgainst passes a second snapshot as the `to` query param', async () => {
		const fetchMock = routedFetch({
			'GET /api/v1/documents/d-1/snapshots/diff?from=s-1&to=s-2': {
				added: [],
				removed: [],
				modified: []
			}
		});
		vi.stubGlobal('fetch', fetchMock);
		const vm = createHistory('d-1');

		await vm.diffAgainst('s-1', 's-2');

		expect(vm.diff).not.toBeNull();
	});

	it('rename updates the label of the matching version', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/documents/d-1/snapshots': [SNAP('s-1', 1)],
				'PATCH /api/v1/documents/d-1/snapshots/s-1': SNAP('s-1', 1, { label: 'Final' })
			})
		);
		const vm = createHistory('d-1');
		await vm.load();

		await vm.rename('s-1', 'Final');

		expect(vm.versions.find((v) => v.id === 's-1')?.label).toBe('Final');
		expect(vm.error).toBeNull();
	});

	it('restore records a new version and reloads the timeline', async () => {
		let listing = [SNAP('s-1', 1)];
		const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
			const key = `${init?.method ?? 'GET'} ${url}`;
			if (key === 'POST /api/v1/documents/d-1/snapshots/s-1/restore') {
				listing = [SNAP('s-1', 1), SNAP('s-2', 2, { restored_from: 's-1' })];
				return { ok: true, status: 200, json: async () => listing[1] };
			}
			if (key === 'GET /api/v1/documents/d-1/snapshots') {
				return { ok: true, status: 200, json: async () => listing };
			}
			throw new Error(`unrouted: ${key}`);
		}) as unknown as typeof fetch;
		vi.stubGlobal('fetch', fetchMock);
		const vm = createHistory('d-1');
		await vm.load();

		await vm.restore('s-1');

		expect(vm.versions.map((v) => v.id)).toEqual(['s-2', 's-1']);
	});

	it('surfaces an error without throwing', async () => {
		vi.stubGlobal('fetch', failingFetch(403, 'forbidden'));
		const vm = createHistory('d-1');

		await vm.load();

		expect(vm.error).toBe('403: forbidden');
		expect(vm.versions).toEqual([]);
	});
});
