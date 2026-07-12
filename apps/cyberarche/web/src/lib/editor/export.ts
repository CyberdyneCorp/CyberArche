/** Client-side document export: serialize the block tree to Markdown, table
 * blocks to CSV, and trigger a file download. PDF uses the browser's print
 * (a print stylesheet shows only the document), so math/mermaid/images render
 * exactly as on screen without a server round-trip. */

import type { BlockData } from './registry';

export type ExportFormat = 'pdf' | 'markdown' | 'csv';

const str = (v: unknown): string => (v == null ? '' : String(v));

/** Render a database block as a Markdown table (select values resolved to option
 * names). */
function databaseToMarkdown(data: Record<string, unknown>): string {
	const db = data.db as
		| {
				properties: { id: string; name: string; type: string; options?: { id: string; name: string }[] }[];
				rows: { values: Record<string, unknown> }[];
		  }
		| undefined;
	if (!db?.properties?.length) return '';
	const cell = (p: (typeof db.properties)[number], v: unknown): string => {
		if (p.type === 'select') return p.options?.find((o) => o.id === v)?.name ?? '';
		if (p.type === 'checkbox') return v ? '✓' : '';
		return str(v);
	};
	const header = `| ${db.properties.map((p) => str(p.name)).join(' | ')} |`;
	const rule = `| ${db.properties.map(() => '---').join(' | ')} |`;
	const body = (db.rows ?? []).map(
		(r) => `| ${db.properties.map((p) => cell(p, r.values?.[p.id])).join(' | ')} |`
	);
	return [header, rule, ...body].join('\n');
}

function tableToMarkdown(data: Record<string, unknown>): string {
	const header = (data.header as unknown[]) ?? [];
	const rows = (data.rows as unknown[][]) ?? [];
	const esc = (c: unknown) => str(c).replace(/\|/g, '\\|').replace(/\n/g, ' ');
	if (header.length === 0) return '';
	const head = `| ${header.map(esc).join(' | ')} |`;
	const sep = `| ${header.map(() => '---').join(' | ')} |`;
	const body = rows.map((r) => `| ${r.map(esc).join(' | ')} |`).join('\n');
	return [head, sep, body].filter(Boolean).join('\n');
}

/** Internal (served, membership-gated) image URLs referenced by image blocks. */
export function internalImageUrls(blocks: BlockData[]): string[] {
	const urls = new Set<string>();
	for (const b of blocks) {
		if (b.type === 'image') {
			const url = str((b.data ?? {}).url);
			if (url.startsWith('/api/')) urls.add(url);
		}
	}
	return [...urls];
}

/** Read a Blob as a base64 data URI (for inlining images into Markdown). */
export function blobToDataUrl(blob: Blob): Promise<string> {
	return new Promise((resolve, reject) => {
		const reader = new FileReader();
		reader.onload = () => resolve(String(reader.result));
		reader.onerror = () => reject(reader.error);
		reader.readAsDataURL(blob);
	});
}

/** Serialize the document (title + blocks) to Markdown. When `images` maps an
 * image URL to a data URI, that image is inlined so the file is self-contained. */
export function toMarkdown(
	title: string,
	blocks: BlockData[],
	images?: Map<string, string>
): string {
	const out: string[] = [];
	if (title.trim()) out.push(`# ${title.trim()}`, '');
	for (const block of blocks) {
		const d = block.data ?? {};
		switch (block.type) {
			case 'heading':
				out.push(`${'#'.repeat(Math.min(Number(d.level) || 1, 6))} ${str(d.text)}`, '');
				break;
			case 'bulleted_list':
				out.push(`- ${str(d.text)}`, '');
				break;
			case 'numbered_list':
				out.push(`1. ${str(d.text)}`, '');
				break;
			case 'todo':
				out.push(`- [${d.checked ? 'x' : ' '}] ${str(d.text)}`, '');
				break;
			case 'quote':
			case 'callout':
				out.push(`> ${str(d.text)}`, '');
				break;
			case 'divider':
				out.push('---', '');
				break;
			case 'code':
				out.push('```' + str(d.language), str(d.source), '```', '');
				break;
			case 'latex':
				out.push('$$', str(d.source), '$$', '');
				break;
			case 'mermaid':
				out.push('```mermaid', str(d.source), '```', '');
				break;
			case 'image': {
				const url = str(d.url);
				// Inline our served images as data URIs when resolved, so the
				// exported Markdown renders them outside CyberArche.
				out.push(`![${str(d.alt)}](${images?.get(url) ?? url})`, '');
				break;
			}
			case 'embed':
				out.push(`[${str(d.url)}](${str(d.url)})`, '');
				break;
			case 'table':
				out.push(tableToMarkdown(d), '');
				break;
			case 'database':
				out.push(databaseToMarkdown(d), '');
				break;
			case 'whiteboard':
			case 'excalidraw':
				out.push('_(whiteboard — open in CyberArche to view)_', '');
				break;
			default:
				if (d.text) out.push(str(d.text), '');
		}
	}
	return out.join('\n').replace(/\n{3,}/g, '\n\n').trim() + '\n';
}

function csvCell(value: unknown): string {
	const s = str(value);
	return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

/** Serialize the document's table blocks to CSV (multiple tables blank-separated).
 * Returns '' when the document has no tables. */
export function tablesToCsv(blocks: BlockData[]): string {
	const tables = blocks.filter((b) => b.type === 'table');
	return tables
		.map((b) => {
			const d = b.data ?? {};
			const rows = [(d.header as unknown[]) ?? [], ...((d.rows as unknown[][]) ?? [])];
			return rows.map((r) => r.map(csvCell).join(',')).join('\r\n');
		})
		.filter(Boolean)
		.join('\r\n\r\n');
}

export function hasTables(blocks: BlockData[]): boolean {
	return blocks.some((b) => b.type === 'table');
}

/** Trigger a browser download of text content. */
export function downloadTextFile(filename: string, content: string, mime: string): void {
	const blob = new Blob([content], { type: `${mime};charset=utf-8` });
	const url = URL.createObjectURL(blob);
	const link = document.createElement('a');
	link.href = url;
	link.download = filename;
	document.body.appendChild(link);
	link.click();
	link.remove();
	URL.revokeObjectURL(url);
}

export function safeFilename(title: string): string {
	const base = title.trim().replace(/[^\w.-]+/g, '-').replace(/^-+|-+$/g, '');
	return base || 'document';
}
