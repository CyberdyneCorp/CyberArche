import { afterEach, describe, expect, it, vi } from 'vitest';

import {
	blobToDataUrl,
	downloadTextFile,
	hasTables,
	internalImageUrls,
	safeFilename,
	tablesToCsv,
	toMarkdown
} from './export';
import type { BlockData } from './registry';

const block = (type: string, data: Record<string, unknown>): BlockData => ({
	id: type,
	type,
	data
});

describe('toMarkdown', () => {
	it('serializes headings, text, lists, todos, and rules', () => {
		const md = toMarkdown('My Doc', [
			block('heading', { text: 'Intro', level: 2 }),
			block('paragraph', { text: 'Hello world.' }),
			block('bulleted_list', { text: 'one' }),
			block('numbered_list', { text: 'first' }),
			block('todo', { text: 'do it', checked: true }),
			block('divider', {})
		]);
		expect(md).toContain('# My Doc');
		expect(md).toContain('## Intro');
		expect(md).toContain('Hello world.');
		expect(md).toContain('- one');
		expect(md).toContain('1. first');
		expect(md).toContain('- [x] do it');
		expect(md).toContain('---');
	});

	it('fences code/mermaid, wraps latex, and links images/embeds', () => {
		const md = toMarkdown('', [
			block('code', { source: 'print(1)', language: 'python' }),
			block('mermaid', { source: 'graph TD; A-->B' }),
			block('latex', { source: '\\frac{1}{x}' }),
			block('image', { url: '/api/v1/x', alt: 'plot' }),
			block('embed', { url: 'https://youtu.be/abc' })
		]);
		expect(md).toContain('```python\nprint(1)\n```');
		expect(md).toContain('```mermaid\ngraph TD; A-->B\n```');
		expect(md).toContain('$$\n\\frac{1}{x}\n$$');
		expect(md).toContain('![plot](/api/v1/x)');
		expect(md).toContain('[https://youtu.be/abc](https://youtu.be/abc)');
	});

	it('inlines internal images as data URIs when provided; keeps external URLs', () => {
		const blocks = [
			block('image', { url: '/api/v1/workspaces/w/files/1', alt: 'mine' }),
			block('image', { url: 'https://example.com/x.png', alt: 'ext' })
		];
		expect(internalImageUrls(blocks)).toEqual(['/api/v1/workspaces/w/files/1']);
		const images = new Map([['/api/v1/workspaces/w/files/1', 'data:image/png;base64,AAA']]);
		const md = toMarkdown('', blocks, images);
		expect(md).toContain('![mine](data:image/png;base64,AAA)');
		expect(md).toContain('![ext](https://example.com/x.png)'); // external untouched
	});

	it('renders a table block as a markdown table', () => {
		const md = toMarkdown('', [
			block('table', { header: ['a', 'b'], rows: [['1', '2']] })
		]);
		expect(md).toContain('| a | b |');
		expect(md).toContain('| --- | --- |');
		expect(md).toContain('| 1 | 2 |');
	});

	it('serializes quotes, callouts, and whiteboard placeholders', () => {
		const md = toMarkdown('', [
			block('quote', { text: 'wise words' }),
			block('callout', { text: 'heads up' }),
			block('whiteboard', {}),
			block('excalidraw', {})
		]);
		expect(md).toContain('> wise words');
		expect(md).toContain('> heads up');
		expect(md.match(/_\(whiteboard — open in CyberArche to view\)_/g)).toHaveLength(2);
	});

	it('clamps heading levels to 1..6 and renders unchecked todos', () => {
		const md = toMarkdown('', [
			block('heading', { text: 'Deep', level: 9 }),
			block('heading', { text: 'Top' }),
			block('todo', { text: 'later', checked: false })
		]);
		expect(md).toContain('###### Deep');
		expect(md).toContain('# Top');
		expect(md).toContain('- [ ] later');
	});

	it('skips unknown blocks without text and tolerates missing data', () => {
		const md = toMarkdown('Title', [
			block('mystery', {}),
			{ id: 'x', type: 'mystery', data: null as unknown as Record<string, unknown> },
			block('mystery', { text: 'still shown' })
		]);
		expect(md).toBe('# Title\n\nstill shown\n');
	});

	it('renders a database block with select, checkbox, and missing values', () => {
		const md = toMarkdown('', [
			block('database', {
				db: {
					properties: [
						{ id: 'p1', name: 'Name', type: 'text' },
						{ id: 'p2', name: 'Status', type: 'select', options: [{ id: 'o1', name: 'Open' }] },
						{ id: 'p3', name: 'Done', type: 'checkbox' },
						{ id: 'p4', name: 'Tag', type: 'select' } // no options
					],
					rows: [
						{ values: { p1: 'Task A', p2: 'o1', p3: true, p4: 'o9' } },
						{ values: { p1: 'Task B', p2: 'missing', p3: false } },
						{} // row without values
					]
				}
			})
		]);
		expect(md).toContain('| Name | Status | Done | Tag |');
		expect(md).toContain('| --- | --- | --- | --- |');
		expect(md).toContain('| Task A | Open | ✓ |  |');
		expect(md).toContain('| Task B |  |  |  |');
		expect(md).toContain('|  |  |  |  |');
	});

	it('renders empty output for databases without properties or rows', () => {
		expect(toMarkdown('', [block('database', {})])).toBe('\n');
		expect(toMarkdown('', [block('database', { db: { properties: [], rows: [] } })])).toBe('\n');
		const headerOnly = toMarkdown('', [
			block('database', { db: { properties: [{ id: 'p', name: 'N', type: 'text' }] } })
		]);
		expect(headerOnly).toBe('| N |\n| --- |\n');
	});

	it('escapes pipes/newlines in table cells and drops headerless tables', () => {
		const md = toMarkdown('', [
			block('table', { header: ['a|b', 'line1\nline2'], rows: [['x|y', 'p\nq']] }),
			block('table', { header: [], rows: [['ignored']] }),
			block('table', { header: ['only'] }) // no rows
		]);
		expect(md).toContain('| a\\|b | line1 line2 |');
		expect(md).toContain('| x\\|y | p q |');
		expect(md).not.toContain('ignored');
		expect(md).toContain('| only |\n| --- |');
	});
});

describe('internalImageUrls', () => {
	it('dedupes urls and ignores non-image or external blocks', () => {
		const urls = internalImageUrls([
			block('image', { url: '/api/v1/files/1' }),
			block('image', { url: '/api/v1/files/1' }),
			block('image', { url: 'https://ext.example/x.png' }),
			{ id: 'i', type: 'image', data: null as unknown as Record<string, unknown> },
			block('paragraph', { text: '/api/v1/files/2' })
		]);
		expect(urls).toEqual(['/api/v1/files/1']);
	});
});

describe('blobToDataUrl', () => {
	it('resolves a base64 data URI', async () => {
		const dataUrl = await blobToDataUrl(new Blob(['hi'], { type: 'text/plain' }));
		expect(dataUrl).toBe('data:text/plain;base64,aGk=');
	});

	it('rejects when the reader errors', async () => {
		class FailingReader {
			onload: (() => void) | null = null;
			onerror: (() => void) | null = null;
			error = new Error('read failed');
			readAsDataURL() {
				queueMicrotask(() => this.onerror?.());
			}
		}
		vi.stubGlobal('FileReader', FailingReader);
		try {
			await expect(blobToDataUrl(new Blob(['x']))).rejects.toThrow('read failed');
		} finally {
			vi.unstubAllGlobals();
		}
	});
});

describe('tablesToCsv', () => {
	it('exports table blocks and escapes cells; empty when no tables', () => {
		const blocks = [
			block('paragraph', { text: 'x' }),
			block('table', { header: ['name', 'note'], rows: [['ada', 'a, b'], ['grace', 'say "hi"']] })
		];
		expect(hasTables(blocks)).toBe(true);
		const csv = tablesToCsv(blocks);
		expect(csv).toContain('name,note');
		expect(csv).toContain('ada,"a, b"');
		expect(csv).toContain('grace,"say ""hi"""');
		expect(tablesToCsv([block('paragraph', { text: 'x' })])).toBe('');
	});

	it('separates multiple tables, quotes newlines, and drops empty tables', () => {
		expect(hasTables([block('paragraph', { text: 'x' })])).toBe(false);
		const csv = tablesToCsv([
			block('table', { header: ['a'], rows: [['line1\nline2']] }),
			block('table', {}), // no header/rows -> empty, filtered out
			block('table', { header: ['b'], rows: [['2']] })
		]);
		expect(csv).toBe('a\r\n"line1\nline2"\r\n\r\nb\r\n2');
	});
});

describe('downloadTextFile', () => {
	afterEach(() => vi.restoreAllMocks());

	it('creates, clicks, and cleans up a download link', () => {
		let captured: Blob | undefined;
		URL.createObjectURL = vi.fn((blob: Blob) => {
			captured = blob;
			return 'blob:doc';
		});
		URL.revokeObjectURL = vi.fn();
		let clicked: HTMLAnchorElement | undefined;
		vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
			this: HTMLAnchorElement
		) {
			clicked = this;
			expect(document.body.contains(this)).toBe(true); // attached when clicked
		});

		downloadTextFile('doc.md', '# hi', 'text/markdown');

		expect(clicked?.download).toBe('doc.md');
		expect(clicked?.href).toContain('blob:doc');
		expect(document.body.contains(clicked!)).toBe(false); // removed afterwards
		expect(captured?.type).toBe('text/markdown;charset=utf-8');
		expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:doc');
	});
});

describe('safeFilename', () => {
	it('slugifies the title and falls back', () => {
		expect(safeFilename('Calculus Introduction')).toBe('Calculus-Introduction');
		expect(safeFilename('  ')).toBe('document');
		expect(safeFilename('!!weird/name??')).toBe('weird-name');
		expect(safeFilename('???')).toBe('document');
	});
});
