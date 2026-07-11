/** Export a teamspace/folder as a ZIP of Markdown files (teamspace-export-and-
 * members). Reuses the single-document Markdown exporter (images inlined as data
 * URIs) so a scope export matches an individual document export. */
import { documentBlocks } from '$lib/api/documents';
import { getBlob } from '$lib/api/http';
import type { BlockData } from '$lib/editor/registry';

import { blobToDataUrl, internalImageUrls, safeFilename, toMarkdown } from './export';

async function inlineImages(blocks: BlockData[]): Promise<Map<string, string>> {
	const map = new Map<string, string>();
	for (const url of internalImageUrls(blocks)) {
		try {
			map.set(url, await blobToDataUrl(await getBlob(url)));
		} catch {
			/* skip an image we can't fetch — the link stays in the Markdown */
		}
	}
	return map;
}

/** Build and download a ZIP with one Markdown file per document. Returns the
 * number of documents actually exported. */
export async function exportScopeZip(
	scopeName: string,
	docs: { id: string; title: string }[]
): Promise<number> {
	const { default: JSZip } = await import('jszip');
	const zip = new JSZip();
	const used = new Set<string>();
	let exported = 0;
	for (const doc of docs) {
		let blocks: BlockData[];
		try {
			blocks = (await documentBlocks(doc.id)).blocks;
		} catch {
			continue; // skip a document we can't read
		}
		const base = safeFilename(doc.title || 'Untitled');
		let name = `${base}.md`;
		for (let n = 2; used.has(name); n++) name = `${base}-${n}.md`;
		used.add(name);
		zip.file(name, toMarkdown(doc.title, blocks, await inlineImages(blocks)));
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
