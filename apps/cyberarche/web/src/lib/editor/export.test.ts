import { describe, expect, it } from 'vitest';

import { hasTables, safeFilename, tablesToCsv, toMarkdown } from './export';
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

	it('renders a table block as a markdown table', () => {
		const md = toMarkdown('', [
			block('table', { header: ['a', 'b'], rows: [['1', '2']] })
		]);
		expect(md).toContain('| a | b |');
		expect(md).toContain('| --- | --- |');
		expect(md).toContain('| 1 | 2 |');
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
});

describe('safeFilename', () => {
	it('slugifies the title and falls back', () => {
		expect(safeFilename('Calculus Introduction')).toBe('Calculus-Introduction');
		expect(safeFilename('  ')).toBe('document');
	});
});
