import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
	addComment,
	createShareLink,
	grantOnDocument,
	inviteToWorkspace,
	listComments,
	listShareLinks,
	listSharedWithMe,
	resolveComment,
	revokeShareLink
} from './sharing';

/** Captures every request so each client's URL/method/body shape is asserted. */
function capturingFetch(body: unknown = null) {
	const calls: Array<{ url: string; method: string; body: unknown }> = [];
	const fn = vi.fn(async (url: string, init?: RequestInit) => {
		calls.push({
			url,
			method: init?.method ?? 'GET',
			body: init?.body ? JSON.parse(String(init.body)) : undefined
		});
		return { ok: true, status: 200, json: async () => body };
	}) as unknown as typeof fetch;
	return { fn, calls };
}

describe('sharing API client', () => {
	beforeEach(() => vi.restoreAllMocks());

	it('inviteToWorkspace posts the user and role to the workspace invites endpoint', async () => {
		const { fn, calls } = capturingFetch();
		vi.stubGlobal('fetch', fn);

		await inviteToWorkspace('ws-1', 'bob', 'editor');

		expect(calls).toEqual([
			{
				url: '/api/v1/workspaces/ws-1/invites',
				method: 'POST',
				body: { user_id: 'bob', role: 'editor' }
			}
		]);
	});

	it('grantOnDocument posts the user and role to the document grants endpoint', async () => {
		const { fn, calls } = capturingFetch();
		vi.stubGlobal('fetch', fn);

		await grantOnDocument('doc-1', 'carol', 'viewer');

		expect(calls).toEqual([
			{
				url: '/api/v1/documents/doc-1/grants',
				method: 'POST',
				body: { user_id: 'carol', role: 'viewer' }
			}
		]);
	});

	it('createShareLink posts the permission and returns the created link', async () => {
		const link = {
			id: 'link-1',
			document_id: 'doc-1',
			permission: 'view',
			created_at: '2026-01-01T00:00:00Z',
			expires_at: null,
			revoked: false
		};
		const { fn, calls } = capturingFetch(link);
		vi.stubGlobal('fetch', fn);

		expect(await createShareLink('doc-1', 'view')).toEqual(link);
		expect(calls).toEqual([
			{
				url: '/api/v1/documents/doc-1/share-links',
				method: 'POST',
				body: { permission: 'view' }
			}
		]);
	});

	it('listShareLinks gets the document share links', async () => {
		const { fn, calls } = capturingFetch([]);
		vi.stubGlobal('fetch', fn);

		expect(await listShareLinks('doc-1')).toEqual([]);
		expect(calls).toEqual([
			{ url: '/api/v1/documents/doc-1/share-links', method: 'GET', body: undefined }
		]);
	});

	it('revokeShareLink deletes the specific link', async () => {
		const { fn, calls } = capturingFetch({ id: 'link-1', revoked: true });
		vi.stubGlobal('fetch', fn);

		expect(await revokeShareLink('doc-1', 'link-1')).toMatchObject({ revoked: true });
		expect(calls).toEqual([
			{ url: '/api/v1/documents/doc-1/share-links/link-1', method: 'DELETE', body: undefined }
		]);
	});

	it('addComment posts the block and body', async () => {
		const comment = {
			id: 'c-1',
			block_id: 'b-1',
			author_id: 'alice',
			body: 'Nice',
			created_at: '2026-01-01T00:00:00Z',
			resolved: false
		};
		const { fn, calls } = capturingFetch(comment);
		vi.stubGlobal('fetch', fn);

		expect(await addComment('doc-1', 'b-1', 'Nice')).toEqual(comment);
		expect(calls).toEqual([
			{
				url: '/api/v1/documents/doc-1/comments',
				method: 'POST',
				body: { block_id: 'b-1', body: 'Nice' }
			}
		]);
	});

	it('listComments gets the document comments', async () => {
		const { fn, calls } = capturingFetch([]);
		vi.stubGlobal('fetch', fn);

		expect(await listComments('doc-1')).toEqual([]);
		expect(calls).toEqual([
			{ url: '/api/v1/documents/doc-1/comments', method: 'GET', body: undefined }
		]);
	});

	it('resolveComment posts to the resolve endpoint with no body', async () => {
		const { fn, calls } = capturingFetch({ id: 'c-1', resolved: true });
		vi.stubGlobal('fetch', fn);

		expect(await resolveComment('doc-1', 'c-1')).toMatchObject({ resolved: true });
		expect(calls).toEqual([
			{ url: '/api/v1/documents/doc-1/comments/c-1/resolve', method: 'POST', body: undefined }
		]);
	});

	it('listSharedWithMe gets the shared-with-me documents', async () => {
		const { fn, calls } = capturingFetch([{ id: 'd-1' }]);
		vi.stubGlobal('fetch', fn);

		expect(await listSharedWithMe()).toEqual([{ id: 'd-1' }]);
		expect(calls).toEqual([{ url: '/api/v1/shared', method: 'GET', body: undefined }]);
	});
});
