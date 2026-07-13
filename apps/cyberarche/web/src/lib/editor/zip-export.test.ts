import JSZip from 'jszip';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { documentBlocks } from '$lib/api/documents';
import { getBlob } from '$lib/api/http';
import type { BlockData } from '$lib/editor/registry';

import { exportScopeZip } from './zip-export';

vi.mock('$lib/api/documents', () => ({ documentBlocks: vi.fn() }));
vi.mock('$lib/api/http', () => ({ getBlob: vi.fn() }));

const documentBlocksMock = vi.mocked(documentBlocks);
const getBlobMock = vi.mocked(getBlob);

const block = (type: string, data: Record<string, unknown>): BlockData => ({
	id: type,
	type,
	data
});

const paragraph = (text: string) => block('paragraph', { text });
const image = (url: string, alt = 'img') => block('image', { url, alt });

/** blocks per document id, wired into the documentBlocks mock. */
function stubDocuments(byId: Record<string, BlockData[]>) {
	documentBlocksMock.mockImplementation(async (id: string) => {
		const blocks = byId[id];
		if (!blocks) throw new Error(`unreadable: ${id}`);
		return { blocks };
	});
}

let downloadedBlob: Blob | undefined;
let downloadName: string | undefined;

async function readZip(): Promise<Record<string, string>> {
	expect(downloadedBlob).toBeDefined();
	const zip = await JSZip.loadAsync(await downloadedBlob!.arrayBuffer());
	const out: Record<string, string> = {};
	for (const name of Object.keys(zip.files)) {
		out[name] = await zip.files[name].async('text');
	}
	return out;
}

describe('exportScopeZip', () => {
	beforeEach(() => {
		vi.restoreAllMocks();
		documentBlocksMock.mockReset();
		getBlobMock.mockReset();
		downloadedBlob = undefined;
		downloadName = undefined;
		URL.createObjectURL = vi.fn((blob: Blob) => {
			downloadedBlob = blob;
			return 'blob:zip';
		});
		URL.revokeObjectURL = vi.fn();
		vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
			this: HTMLAnchorElement
		) {
			downloadName = this.download;
		});
	});

	it('writes one markdown file per document, deduping filenames', async () => {
		stubDocuments({
			d1: [paragraph('first')],
			d2: [paragraph('second')],
			d3: [paragraph('third')],
			d4: [paragraph('untitled body')]
		});

		const exported = await exportScopeZip('Team Alpha', [
			{ id: 'd1', title: 'Notes' },
			{ id: 'd2', title: 'Notes' },
			{ id: 'd3', title: 'Notes' },
			{ id: 'd4', title: '' }
		]);

		expect(exported).toBe(4);
		expect(downloadName).toBe('Team-Alpha.zip');
		expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:zip');
		const files = await readZip();
		expect(Object.keys(files).sort()).toEqual([
			'Notes-2.md',
			'Notes-3.md',
			'Notes.md',
			'Untitled.md'
		]);
		expect(files['Notes.md']).toContain('# Notes');
		expect(files['Notes.md']).toContain('first');
		expect(files['Notes-3.md']).toContain('third');
		expect(files['Untitled.md']).toContain('untitled body');
	});

	it('skips documents whose blocks cannot be read', async () => {
		stubDocuments({ ok: [paragraph('kept')] }); // 'broken' rejects

		const exported = await exportScopeZip('Scope', [
			{ id: 'broken', title: 'Broken' },
			{ id: 'ok', title: 'Kept' }
		]);

		expect(exported).toBe(1);
		const files = await readZip();
		expect(Object.keys(files)).toEqual(['Kept.md']);
	});

	it('stores each internal image once under assets/ and rewrites links', async () => {
		stubDocuments({
			d1: [image('/api/v1/files/abc?sig=1', 'shared')],
			d2: [image('/api/v1/files/abc?sig=1', 'shared'), image('/api/v1/files/def', 'plain')]
		});
		getBlobMock.mockImplementation(async (url: string) =>
			url.includes('abc')
				? new Blob(['png-bytes'], { type: 'image/png' })
				: new Blob(['raw-bytes'], { type: 'application/octet-stream' })
		);

		const exported = await exportScopeZip('Pics', [
			{ id: 'd1', title: 'One' },
			{ id: 'd2', title: 'Two' }
		]);

		expect(exported).toBe(2);
		// shared image fetched once despite appearing in both documents
		expect(getBlobMock).toHaveBeenCalledTimes(2);
		const files = await readZip();
		expect(files['assets/abc.png']).toBe('png-bytes');
		// unknown mime and no URL extension falls back to .bin
		expect(files['assets/def.bin']).toBe('raw-bytes');
		expect(files['One.md']).toContain('![shared](assets/abc.png)');
		expect(files['Two.md']).toContain('![plain](assets/def.bin)');
	});

	it('infers the extension from the URL when the mime type is unknown', async () => {
		stubDocuments({
			d1: [image('/api/v1/files/pic.JPG?x=1'), image('/api/files/')]
		});
		getBlobMock.mockImplementation(async (url: string) =>
			url.endsWith('/')
				? new Blob(['x'], { type: 'image/webp' })
				: new Blob(['y'], { type: 'application/octet-stream' })
		);

		await exportScopeZip('S', [{ id: 'd1', title: 'Doc' }]);

		const files = await readZip();
		expect(files['assets/pic.JPG.jpg']).toBe('y'); // extension from URL, lowercased
		expect(files['assets/file.webp']).toBe('x'); // empty file id falls back to "file"
	});

	it('keeps the original URL when an image cannot be fetched', async () => {
		stubDocuments({ d1: [image('/api/v1/files/gone', 'lost')] });
		getBlobMock.mockRejectedValue(new Error('403'));

		const exported = await exportScopeZip('S', [{ id: 'd1', title: 'Doc' }]);

		expect(exported).toBe(1);
		const files = await readZip();
		expect(Object.keys(files)).toEqual(['Doc.md']);
		expect(files['Doc.md']).toContain('![lost](/api/v1/files/gone)');
	});

	it('exports an empty zip and falls back to export.zip for a blank scope name', async () => {
		stubDocuments({});

		const exported = await exportScopeZip('', []);

		expect(exported).toBe(0);
		expect(downloadName).toBe('export.zip');
		expect(await readZip()).toEqual({});
	});
});
