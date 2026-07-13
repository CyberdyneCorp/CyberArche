import { describe, expect, it, vi } from 'vitest';

import { createLinkIndex } from './link-index.svelte';

const doc = (id: string, title: string) => ({
	id,
	workspace_id: 'w1',
	title,
	parent_id: null,
	position: 0,
	created_by: 'alice',
	created_at: '',
	updated_at: '',
	trashed: false,
	teamspace_id: null
});

describe('link index', () => {
	it('resolves titles case-insensitively and filters matches', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async () => ({
				ok: true,
				status: 200,
				json: async () => [doc('d1', 'Calculus Introduction'), doc('d2', 'Algebra')]
			})) as unknown as typeof fetch
		);

		const idx = createLinkIndex();
		await idx.load('w1');

		expect(idx.hrefFor('calculus introduction')).toBe('/w/w1/d/d1');
		expect(idx.hrefFor('  Algebra ')).toBe('/w/w1/d/d2'); // trims + case-insensitive
		expect(idx.hrefFor('nonexistent')).toBeNull();
		expect(idx.matches('alg').map((d) => d.id)).toEqual(['d2']);
		expect(idx.matches('').length).toBe(2); // empty query = all
	});

	it('refresh is a no-op before load and refetches after', async () => {
		let results = [doc('d1', 'One')];
		const fetchMock = vi.fn(async () => ({
			ok: true,
			status: 200,
			json: async () => results
		}));
		vi.stubGlobal('fetch', fetchMock as unknown as typeof fetch);

		const idx = createLinkIndex();
		await idx.refresh(); // no workspace loaded yet
		expect(fetchMock).not.toHaveBeenCalled();
		expect(idx.all).toEqual([]);

		await idx.load('w1');
		expect(idx.all.map((d) => d.id)).toEqual(['d1']);

		results = [doc('d1', 'One'), doc('d2', 'Two')];
		await idx.refresh();
		expect(idx.all.map((d) => d.id)).toEqual(['d1', 'd2']);
	});

	it('matches caps results at the limit', async () => {
		const many = Array.from({ length: 10 }, (_, i) => doc(`d${i}`, `Note ${i}`));
		vi.stubGlobal(
			'fetch',
			vi.fn(async () => ({ ok: true, status: 200, json: async () => many })) as unknown as typeof fetch
		);

		const idx = createLinkIndex();
		await idx.load('w1');

		expect(idx.matches('note')).toHaveLength(8); // default cap
		expect(idx.matches('note', 2)).toHaveLength(2);
	});
});
