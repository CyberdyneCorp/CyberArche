import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
	backlinks,
	createDocument,
	documentBlocks,
	getDocument,
	listChildren,
	listTrashed,
	purgeDocument,
	restoreDocument,
	retitleDocument,
	searchDocuments,
	trashDocument
} from './documents';

const DOCUMENT = {
	id: 'doc-1',
	workspace_id: 'ws-1',
	title: 'Notes',
	parent_id: null,
	position: 0,
	created_by: 'alice',
	created_at: '2026-01-01T00:00:00Z',
	updated_at: '2026-01-01T00:00:00Z',
	trashed: false,
	teamspace_id: null
};

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

describe('documents API client', () => {
	beforeEach(() => vi.restoreAllMocks());

	it('createDocument defaults title to empty and parent/teamspace to null', async () => {
		const { fn, calls } = capturingFetch(DOCUMENT);
		vi.stubGlobal('fetch', fn);

		expect(await createDocument('ws-1')).toEqual(DOCUMENT);
		expect(calls).toEqual([
			{
				url: '/api/v1/documents',
				method: 'POST',
				body: { workspace_id: 'ws-1', title: '', parent_id: null, teamspace_id: null }
			}
		]);
	});

	it('createDocument posts the title, parent and teamspace when given', async () => {
		const { fn, calls } = capturingFetch(DOCUMENT);
		vi.stubGlobal('fetch', fn);

		await createDocument('ws-1', 'Roadmap', 'doc-parent', 'ts-1');

		expect(calls).toEqual([
			{
				url: '/api/v1/documents',
				method: 'POST',
				body: {
					workspace_id: 'ws-1',
					title: 'Roadmap',
					parent_id: 'doc-parent',
					teamspace_id: 'ts-1'
				}
			}
		]);
	});

	it('getDocument GETs by id', async () => {
		const { fn, calls } = capturingFetch(DOCUMENT);
		vi.stubGlobal('fetch', fn);

		expect(await getDocument('doc-1')).toEqual(DOCUMENT);
		expect(calls).toEqual([{ url: '/api/v1/documents/doc-1', method: 'GET', body: undefined }]);
	});

	it('documentBlocks GETs the block tree', async () => {
		const blocks = { blocks: [{ id: 'b-1', type: 'paragraph', data: { text: 'hi' } }] };
		const { fn, calls } = capturingFetch(blocks);
		vi.stubGlobal('fetch', fn);

		expect(await documentBlocks('doc-1')).toEqual(blocks);
		expect(calls).toEqual([
			{ url: '/api/v1/documents/doc-1/blocks', method: 'GET', body: undefined }
		]);
	});

	it('searchDocuments defaults to an empty query and limit 50', async () => {
		const { fn, calls } = capturingFetch([]);
		vi.stubGlobal('fetch', fn);

		expect(await searchDocuments('ws-1')).toEqual([]);
		expect(calls).toEqual([
			{ url: '/api/v1/workspaces/ws-1/search?q=&limit=50', method: 'GET', body: undefined }
		]);
	});

	it('searchDocuments URL-encodes the query and passes the limit', async () => {
		const { fn, calls } = capturingFetch([DOCUMENT]);
		vi.stubGlobal('fetch', fn);

		expect(await searchDocuments('ws-1', 'road map', 5)).toEqual([DOCUMENT]);
		expect(calls).toEqual([
			{ url: '/api/v1/workspaces/ws-1/search?q=road+map&limit=5', method: 'GET', body: undefined }
		]);
	});

	it('backlinks GETs the referencing documents', async () => {
		const { fn, calls } = capturingFetch([DOCUMENT]);
		vi.stubGlobal('fetch', fn);

		expect(await backlinks('doc-1')).toEqual([DOCUMENT]);
		expect(calls).toEqual([
			{ url: '/api/v1/documents/doc-1/backlinks', method: 'GET', body: undefined }
		]);
	});

	it('listTrashed GETs the workspace trash', async () => {
		const { fn, calls } = capturingFetch([]);
		vi.stubGlobal('fetch', fn);

		expect(await listTrashed('ws-1')).toEqual([]);
		expect(calls).toEqual([
			{ url: '/api/v1/workspaces/ws-1/trash', method: 'GET', body: undefined }
		]);
	});

	it('listChildren omits parent_id for root documents', async () => {
		const { fn, calls } = capturingFetch([DOCUMENT]);
		vi.stubGlobal('fetch', fn);

		expect(await listChildren('ws-1')).toEqual([DOCUMENT]);
		expect(calls).toEqual([
			{ url: '/api/v1/documents?workspace_id=ws-1', method: 'GET', body: undefined }
		]);
	});

	it('listChildren scopes to the parent when given', async () => {
		const { fn, calls } = capturingFetch([]);
		vi.stubGlobal('fetch', fn);

		await listChildren('ws-1', 'doc-parent');

		expect(calls).toEqual([
			{
				url: '/api/v1/documents?workspace_id=ws-1&parent_id=doc-parent',
				method: 'GET',
				body: undefined
			}
		]);
	});

	it('retitleDocument PATCHes the title endpoint', async () => {
		const { fn, calls } = capturingFetch({ ...DOCUMENT, title: 'Renamed' });
		vi.stubGlobal('fetch', fn);

		expect(await retitleDocument('doc-1', 'Renamed')).toMatchObject({ title: 'Renamed' });
		expect(calls).toEqual([
			{ url: '/api/v1/documents/doc-1/title', method: 'PATCH', body: { title: 'Renamed' } }
		]);
	});

	it('trashDocument DELETEs the document', async () => {
		const { fn, calls } = capturingFetch({ ...DOCUMENT, trashed: true });
		vi.stubGlobal('fetch', fn);

		expect(await trashDocument('doc-1')).toMatchObject({ trashed: true });
		expect(calls).toEqual([{ url: '/api/v1/documents/doc-1', method: 'DELETE', body: undefined }]);
	});

	it('restoreDocument POSTs to the restore endpoint with no body', async () => {
		const { fn, calls } = capturingFetch(DOCUMENT);
		vi.stubGlobal('fetch', fn);

		expect(await restoreDocument('doc-1')).toEqual(DOCUMENT);
		expect(calls).toEqual([
			{ url: '/api/v1/documents/doc-1/restore', method: 'POST', body: undefined }
		]);
	});

	it('purgeDocument DELETEs the trash entry and returns the purged ids', async () => {
		const { fn, calls } = capturingFetch({ purged: ['doc-1', 'doc-2'] });
		vi.stubGlobal('fetch', fn);

		expect(await purgeDocument('doc-1')).toEqual({ purged: ['doc-1', 'doc-2'] });
		expect(calls).toEqual([
			{ url: '/api/v1/documents/doc-1/trash', method: 'DELETE', body: undefined }
		]);
	});
});
