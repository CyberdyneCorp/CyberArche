/** Export a teamspace/folder as a ZIP of Markdown files (teamspace-export-and-
 * members). Images are written as separate binary files under `assets/` and
 * referenced by relative path from each Markdown file — so the archive holds the
 * documents plus their pictures, not one giant inlined file. */
import { documentBlocks } from '$lib/api/documents';
import { getBlob } from '$lib/api/http';
import type { BlockData } from '$lib/editor/registry';

import { internalImageUrls, safeFilename, toMarkdown } from './export';

const _EXT: Record<string, string> = {
	'image/png': 'png',
	'image/jpeg': 'jpg',
	'image/gif': 'gif',
	'image/webp': 'webp',
	'image/svg+xml': 'svg',
	'image/avif': 'avif'
};

function extensionFor(blob: Blob, url: string): string {
	if (_EXT[blob.type]) return _EXT[blob.type];
	const m = url.match(/\.([a-z0-9]+)(?:\?|$)/i);
	return m ? m[1].toLowerCase() : 'bin';
}

/** Build and download a ZIP with one Markdown file per document plus an `assets/`
 * folder of their images. Returns the number of documents exported. */
export async function exportScopeZip(
	scopeName: string,
	docs: { id: string; title: string }[]
): Promise<number> {
	const { default: JSZip } = await import('jszip');
	const zip = new JSZip();
	// url -> relative asset path, shared across documents so a picture used in
	// several documents is stored once.
	const assets = new Map<string, string>();

	async function collectAssets(blocks: BlockData[]): Promise<void> {
		for (const url of internalImageUrls(blocks)) {
			if (assets.has(url)) continue;
			try {
				const blob = await getBlob(url);
				const fileId = url.split('?')[0].split('/').pop() || 'file';
				const path = `assets/${fileId}.${extensionFor(blob, url)}`;
				zip.file(path, blob);
				assets.set(url, path);
			} catch {
				/* leave the original URL in the Markdown if it can't be fetched */
			}
		}
	}

	const used = new Set<string>();
	let exported = 0;
	for (const doc of docs) {
		let blocks: BlockData[];
		try {
			blocks = (await documentBlocks(doc.id)).blocks;
		} catch {
			continue; // skip a document we can't read
		}
		await collectAssets(blocks);
		const base = safeFilename(doc.title || 'Untitled');
		let name = `${base}.md`;
		for (let n = 2; used.has(name); n++) name = `${base}-${n}.md`;
		used.add(name);
		zip.file(name, toMarkdown(doc.title, blocks, assets));
		exported++;
	}
	const blob = await zip.generateAsync({ type: 'blob' });
	const href = URL.createObjectURL(blob);
	const a = document.createElement('a');
	a.href = href;
	a.download = `${safeFilename(scopeName || 'export')}.zip`;
	a.click();
	URL.revokeObjectURL(href);
	return exported;
}
