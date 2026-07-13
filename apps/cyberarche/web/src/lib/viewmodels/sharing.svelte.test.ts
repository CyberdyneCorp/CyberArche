import { beforeEach, describe, expect, it, vi } from 'vitest';

import { createSharing } from './sharing.svelte';

const LINK = (id: string, revoked = false) => ({
	id,
	document_id: 'doc-1',
	permission: 'view',
	created_at: '2026-01-01T00:00:00Z',
	expires_at: null,
	revoked
});

const COMMENT = (id: string, block_id = 'b-1', resolved = false) => ({
	id,
	block_id,
	author_id: 'alice',
	body: `Comment ${id}`,
	created_at: '2026-01-01T00:00:00Z',
	resolved
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

/** Routes like routedFetch, but keys in `denied` respond 403. */
function deniedFetch(routes: Record<string, unknown>, denied: string[]) {
	return vi.fn(async (url: string, init?: RequestInit) => {
		const key = `${init?.method ?? 'GET'} ${url}`;
		if (denied.includes(key)) {
			return { ok: false, status: 403, json: async () => ({ detail: 'forbidden' }) };
		}
		const body = routes[key];
		if (body === undefined) throw new Error(`unrouted: ${key}`);
		return { ok: true, status: 200, json: async () => body };
	}) as unknown as typeof fetch;
}

describe('sharing ViewModel', () => {
	beforeEach(() => vi.restoreAllMocks());

	it('starts empty and exposes the document id', () => {
		const vm = createSharing('ws-1', 'doc-1');

		expect(vm.documentId).toBe('doc-1');
		expect(vm.links).toEqual([]);
		expect(vm.comments).toEqual([]);
		expect(vm.error).toBeNull();
		expect(vm.invited).toBeNull();
	});

	it('load populates comments and share links', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/documents/doc-1/comments': [COMMENT('c-1')],
				'GET /api/v1/documents/doc-1/share-links': [LINK('link-1')]
			})
		);
		const vm = createSharing('ws-1', 'doc-1');
		await vm.load();

		expect(vm.comments.map((c) => c.id)).toEqual(['c-1']);
		expect(vm.links.map((l) => l.id)).toEqual(['link-1']);
		expect(vm.error).toBeNull();
	});

	it('load keeps links empty when the share-links listing is owner-only (403)', async () => {
		vi.stubGlobal(
			'fetch',
			deniedFetch({ 'GET /api/v1/documents/doc-1/comments': [COMMENT('c-1')] }, [
				'GET /api/v1/documents/doc-1/share-links'
			])
		);
		const vm = createSharing('ws-1', 'doc-1');
		await vm.load();

		expect(vm.links).toEqual([]);
		expect(vm.comments.map((c) => c.id)).toEqual(['c-1']);
		// A 403 on links is expected for non-owners, not an error state.
		expect(vm.error).toBeNull();
	});

	it('load surfaces a comments failure but still fetches links', async () => {
		vi.stubGlobal(
			'fetch',
			deniedFetch({ 'GET /api/v1/documents/doc-1/share-links': [LINK('link-1')] }, [
				'GET /api/v1/documents/doc-1/comments'
			])
		);
		const vm = createSharing('ws-1', 'doc-1');
		await vm.load();

		expect(vm.error).toMatch(/403/);
		expect(vm.comments).toEqual([]);
		expect(vm.links.map((l) => l.id)).toEqual(['link-1']);
	});

	it('commentsFor filters by block and hides resolved comments', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/documents/doc-1/comments': [
					COMMENT('c-1', 'b-1'),
					COMMENT('c-2', 'b-2'),
					COMMENT('c-3', 'b-1', true)
				],
				'GET /api/v1/documents/doc-1/share-links': []
			})
		);
		const vm = createSharing('ws-1', 'doc-1');
		await vm.load();

		expect(vm.commentsFor('b-1').map((c) => c.id)).toEqual(['c-1']);
		expect(vm.commentsFor('b-2').map((c) => c.id)).toEqual(['c-2']);
		expect(vm.commentsFor('b-none')).toEqual([]);
	});

	it('invite posts to the workspace and records the invited user', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({ 'POST /api/v1/workspaces/ws-1/invites': {} })
		);
		const vm = createSharing('ws-1', 'doc-1');
		await vm.invite('bob', 'editor');

		expect(vm.invited).toBe('bob');
		expect(vm.error).toBeNull();
	});

	it('a failed invite clears any prior invited user and sets the error', async () => {
		vi.stubGlobal(
			'fetch',
			deniedFetch({ 'POST /api/v1/workspaces/ws-1/invites': {} }, [])
		);
		const vm = createSharing('ws-1', 'doc-1');
		await vm.invite('bob', 'editor');
		expect(vm.invited).toBe('bob');

		vi.stubGlobal('fetch', deniedFetch({}, ['POST /api/v1/workspaces/ws-1/invites']));
		await vm.invite('mallory', 'owner');

		expect(vm.invited).toBeNull();
		expect(vm.error).toMatch(/403/);
	});

	it('grant posts a document-level grant and records the invited user', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({ 'POST /api/v1/documents/doc-1/grants': {} })
		);
		const vm = createSharing('ws-1', 'doc-1');
		await vm.grant('carol', 'viewer');

		expect(vm.invited).toBe('carol');
		expect(vm.error).toBeNull();
	});

	it('a denied grant leaves invited unset and surfaces the error', async () => {
		vi.stubGlobal('fetch', deniedFetch({}, ['POST /api/v1/documents/doc-1/grants']));
		const vm = createSharing('ws-1', 'doc-1');
		await vm.grant('carol', 'viewer');

		expect(vm.invited).toBeNull();
		expect(vm.error).toMatch(/403/);
	});

	it('createLink appends the new link', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/documents/doc-1/comments': [],
				'GET /api/v1/documents/doc-1/share-links': [LINK('link-1')],
				'POST /api/v1/documents/doc-1/share-links': LINK('link-2')
			})
		);
		const vm = createSharing('ws-1', 'doc-1');
		await vm.load();
		await vm.createLink('view');

		expect(vm.links.map((l) => l.id)).toEqual(['link-1', 'link-2']);
	});

	it('a denied createLink sets the error and adds nothing', async () => {
		vi.stubGlobal('fetch', deniedFetch({}, ['POST /api/v1/documents/doc-1/share-links']));
		const vm = createSharing('ws-1', 'doc-1');
		await vm.createLink('edit');

		expect(vm.links).toEqual([]);
		expect(vm.error).toMatch(/403/);
	});

	it('revokeLink swaps in the revoked link and leaves the others untouched', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/documents/doc-1/comments': [],
				'GET /api/v1/documents/doc-1/share-links': [LINK('link-1'), LINK('link-2')],
				'DELETE /api/v1/documents/doc-1/share-links/link-1': LINK('link-1', true)
			})
		);
		const vm = createSharing('ws-1', 'doc-1');
		await vm.load();
		await vm.revokeLink('link-1');

		expect(vm.links.map((l) => [l.id, l.revoked])).toEqual([
			['link-1', true],
			['link-2', false]
		]);
	});

	it('a failed revokeLink keeps the link active and sets the error', async () => {
		vi.stubGlobal(
			'fetch',
			deniedFetch(
				{
					'GET /api/v1/documents/doc-1/comments': [],
					'GET /api/v1/documents/doc-1/share-links': [LINK('link-1')]
				},
				['DELETE /api/v1/documents/doc-1/share-links/link-1']
			)
		);
		const vm = createSharing('ws-1', 'doc-1');
		await vm.load();
		await vm.revokeLink('link-1');

		expect(vm.links[0].revoked).toBe(false);
		expect(vm.error).toMatch(/403/);
	});

	it('linkUrl builds a share URL from the current origin', () => {
		const vm = createSharing('ws-1', 'doc-1');

		expect(vm.linkUrl(LINK('link-1'))).toBe(`${location.origin}/share/link-1`);
	});

	it('comment appends the created comment', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/documents/doc-1/comments': [COMMENT('c-1')],
				'GET /api/v1/documents/doc-1/share-links': [],
				'POST /api/v1/documents/doc-1/comments': COMMENT('c-2', 'b-2')
			})
		);
		const vm = createSharing('ws-1', 'doc-1');
		await vm.load();
		await vm.comment('b-2', 'Comment c-2');

		expect(vm.comments.map((c) => c.id)).toEqual(['c-1', 'c-2']);
		expect(vm.commentsFor('b-2').map((c) => c.id)).toEqual(['c-2']);
	});

	it('a denied comment sets the error and adds nothing', async () => {
		vi.stubGlobal('fetch', deniedFetch({}, ['POST /api/v1/documents/doc-1/comments']));
		const vm = createSharing('ws-1', 'doc-1');
		await vm.comment('b-1', 'nope');

		expect(vm.comments).toEqual([]);
		expect(vm.error).toMatch(/403/);
	});

	it('resolve swaps in the resolved comment, hiding it from its block', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'GET /api/v1/documents/doc-1/comments': [COMMENT('c-1'), COMMENT('c-2')],
				'GET /api/v1/documents/doc-1/share-links': [],
				'POST /api/v1/documents/doc-1/comments/c-1/resolve': COMMENT('c-1', 'b-1', true)
			})
		);
		const vm = createSharing('ws-1', 'doc-1');
		await vm.load();
		await vm.resolve('c-1');

		expect(vm.comments.map((c) => [c.id, c.resolved])).toEqual([
			['c-1', true],
			['c-2', false]
		]);
		expect(vm.commentsFor('b-1').map((c) => c.id)).toEqual(['c-2']);
	});

	it('a failed resolve leaves the comment open and sets the error', async () => {
		vi.stubGlobal(
			'fetch',
			deniedFetch(
				{
					'GET /api/v1/documents/doc-1/comments': [COMMENT('c-1')],
					'GET /api/v1/documents/doc-1/share-links': []
				},
				['POST /api/v1/documents/doc-1/comments/c-1/resolve']
			)
		);
		const vm = createSharing('ws-1', 'doc-1');
		await vm.load();
		await vm.resolve('c-1');

		expect(vm.comments[0].resolved).toBe(false);
		expect(vm.error).toMatch(/403/);
	});

	it('a successful action clears a previous error', async () => {
		vi.stubGlobal('fetch', deniedFetch({}, ['POST /api/v1/documents/doc-1/comments']));
		const vm = createSharing('ws-1', 'doc-1');
		await vm.comment('b-1', 'nope');
		expect(vm.error).toMatch(/403/);

		vi.stubGlobal(
			'fetch',
			routedFetch({ 'POST /api/v1/documents/doc-1/comments': COMMENT('c-1') })
		);
		await vm.comment('b-1', 'Comment c-1');

		expect(vm.error).toBeNull();
		expect(vm.comments.map((c) => c.id)).toEqual(['c-1']);
	});
});
