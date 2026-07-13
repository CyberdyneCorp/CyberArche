import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from './http';
import { uploadImage } from './files';

const UPLOADED = { id: 'file-1', url: '/files/file-1', content_type: 'image/png' };

function mockFetch(status: number, body: unknown) {
	return vi.fn(async () => ({
		ok: status < 400,
		status,
		json: async () => body
	})) as unknown as typeof fetch;
}

describe('files API', () => {
	beforeEach(() => vi.restoreAllMocks());

	it('uploadImage POSTs the file as multipart form data', async () => {
		const fetchMock = mockFetch(200, UPLOADED);
		vi.stubGlobal('fetch', fetchMock);
		const file = new File(['png-bytes'], 'shot.png', { type: 'image/png' });

		const uploaded = await uploadImage('ws-1', file);

		expect(uploaded).toEqual(UPLOADED);
		const [url, init] = (fetchMock as ReturnType<typeof vi.fn>).mock.calls[0];
		expect(url).toBe('/api/v1/workspaces/ws-1/files');
		expect(init.method).toBe('POST');
		expect(init.body).toBeInstanceOf(FormData);
		expect(init.body.get('file')).toBe(file);
		// The Content-Type must stay unset so fetch adds the multipart boundary.
		expect(new Headers(init.headers).get('Content-Type')).toBeNull();
	});

	it('uploadImage surfaces an ApiError on rejection', async () => {
		vi.stubGlobal('fetch', mockFetch(413, { detail: 'too large' }));
		const file = new File(['x'], 'big.png', { type: 'image/png' });

		await expect(uploadImage('ws-1', file)).rejects.toThrow(ApiError);
		await expect(uploadImage('ws-1', file)).rejects.toThrow('413: too large');
	});
});
