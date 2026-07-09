import { describe, expect, it } from 'vitest';

import { renderInline } from './inline';

describe('renderInline', () => {
	it('escapes HTML so user text cannot inject markup', () => {
		expect(renderInline('<script>alert(1)</script>')).not.toContain('<script>');
		expect(renderInline('a < b & c')).toContain('&lt;');
	});

	it('renders bold and italic', () => {
		expect(renderInline('**bold**')).toContain('<strong>bold</strong>');
		expect(renderInline('*italic*')).toContain('<em>italic</em>');
		expect(renderInline('_also_')).toContain('<em>also</em>');
	});

	it('does not treat bold as italic', () => {
		const html = renderInline('**strong**');
		expect(html).toContain('<strong>strong</strong>');
		expect(html).not.toContain('<em>');
	});

	it('renders inline math via KaTeX', () => {
		const html = renderInline('mass is $E = mc^2$ today');
		expect(html).toContain('katex'); // KaTeX emits .katex spans
		expect(html).toContain('today'); // surrounding text preserved
	});

	it('flags invalid math without dropping the source', () => {
		const html = renderInline('$\\frac{1}{$');
		expect(html).toContain('inline-math-error');
		expect(html).toContain('$'); // raw source still shown
	});

	it('leaves an unclosed dollar as literal text', () => {
		const html = renderInline('costs $5 today');
		expect(html).not.toContain('katex');
		expect(html).toContain('$5 today');
	});

	it('treats an escaped dollar as a literal, not a delimiter', () => {
		const html = renderInline('price \\$5 and \\$9');
		expect(html).not.toContain('katex');
		expect(html).toContain('$5 and $9');
	});

	it('renders emphasis and math together', () => {
		const html = renderInline('**F** = $ma$');
		expect(html).toContain('<strong>F</strong>');
		expect(html).toContain('katex');
	});

	it('is empty for empty input', () => {
		expect(renderInline('')).toBe('');
	});
});
