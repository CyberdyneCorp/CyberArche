import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from './http';
import { importFile } from './import';

const DOCS = [{ id: 'doc-1', title: 'Project Plan', parent_id: null, teamspace_id: null }];

function mockFetch(status: number, body: unknown) {
	return vi.fn(async () => ({
		ok: status < 400,
		status,
		json: async () => body
	})) as unknown as typeof fetch;
}

describe('import API', () => {
	beforeEach(() => vi.restoreAllMocks());

	it('importFile POSTs the file as multipart form data and returns docs', async () => {
		const fetchMock = mockFetch(201, DOCS);
		vi.stubGlobal('fetch', fetchMock);
		const file = new File(['# Title'], 'plan.md', { type: 'text/markdown' });

		const docs = await importFile('ws-1', file);

		expect(docs).toEqual(DOCS);
		const [url, init] = (fetchMock as ReturnType<typeof vi.fn>).mock.calls[0];
		expect(url).toBe('/api/v1/workspaces/ws-1/import');
		expect(init.method).toBe('POST');
		expect(init.body).toBeInstanceOf(FormData);
		expect(init.body.get('file')).toBe(file);
		// The Content-Type must stay unset so fetch adds the multipart boundary.
		expect(new Headers(init.headers).get('Content-Type')).toBeNull();
	});

	it('importFile surfaces an ApiError on rejection', async () => {
		vi.stubGlobal('fetch', mockFetch(400, { detail: 'unsupported file type' }));
		const file = new File(['x'], 'bad.xyz', { type: 'application/octet-stream' });

		await expect(importFile('ws-1', file)).rejects.toThrow(ApiError);
		await expect(importFile('ws-1', file)).rejects.toThrow('400: unsupported file type');
	});
});
