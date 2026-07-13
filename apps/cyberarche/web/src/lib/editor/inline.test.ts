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

	it('renders inline code and strikethrough', () => {
		expect(renderInline('use `npm ci` now')).toContain('<code>npm ci</code>');
		expect(renderInline('~~gone~~')).toContain('<del>gone</del>');
	});

	it('does not apply emphasis to markers inside inline code', () => {
		// The `**` inside the code span is literal, not bold.
		const html = renderInline('`a**b`');
		expect(html).toContain('<code>a**b</code>');
		expect(html).not.toContain('<strong>');
	});

	it('renders [label](url) external links with a safe target', () => {
		const html = renderInline('see [Cyberfluids](https://github.com/cyberarche/cyberfluids)');
		expect(html).toContain(
			'<a class="ext-link" href="https://github.com/cyberarche/cyberfluids" target="_blank" rel="noopener noreferrer">Cyberfluids</a>'
		);
	});

	it('does not render an unsafe scheme as a link (falls back to text)', () => {
		const html = renderInline('[x](javascript:alert)');
		expect(html).not.toContain('<a'); // no anchor emitted
		expect(html).not.toContain('href='); // and certainly no dangerous href
	});

	it('renders a wikilink and an external link in the same text', () => {
		const html = renderInline('[[Home]] and [GH](https://github.com)', () => '/w/1/d/2');
		expect(html).toContain('class="wikilink"');
		expect(html).toContain('class="ext-link"');
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

	it('escapes double quotes in the math-error title (F-014 attribute injection)', () => {
		// KaTeX echoes the raw source in its error message; a " must not break out
		// of the title="…" attribute and inject event handlers onto the span.
		const html = renderInline('$\\unknown"onmouseover=alert(1) x$');
		const title = html.match(/title="([^"]*)"/);
		expect(title).not.toBeNull(); // the attribute closes cleanly on a real quote
		// The quote from the echoed source is entity-escaped INSIDE the title, so
		// no attribute breakout: the captured title contains &quot;, not a raw ".
		expect(title![1]).toContain('&quot;onmouseover');
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

	it('renders TeX \\(…\\) inline delimiters as math', () => {
		const html = renderInline('fields \\(\\mathbf{E}\\) and \\(\\mathbf{B}\\)');
		expect(html).toContain('katex');
		expect(html).not.toContain('\\('); // delimiters consumed
	});

	it('renders TeX \\[…\\] inline delimiters as math', () => {
		const html = renderInline('law: \\[ E = mc^2 \\]');
		expect(html).toContain('katex');
		expect(html).not.toContain('\\[');
	});

	it('renders \\mathbf via KaTeX', () => {
		expect(renderInline('$\\mathbf{E}$')).toContain('katex');
	});

	it('renders display math $$…$$ inside a paragraph (regression)', () => {
		// Was shown as raw source because $$ was read as two empty $…$ spans.
		const html = renderInline('Divergence: $$\\nabla \\cdot \\mathbf{F}$$');
		expect(html).toContain('katex-display'); // KaTeX display mode (typeset)
		expect(html).toContain('Divergence:'); // surrounding text kept
		expect(html).not.toContain('$$'); // delimiters consumed, not shown raw
	});

	it('renders TeX \\[…\\] as display math, not inline', () => {
		const html = renderInline('law: \\[ E = mc^2 \\]');
		expect(html).toContain('katex-display');
	});

	it('renders resolved and broken [[wikilinks]]', () => {
		const resolve = (t: string) =>
			t.toLowerCase() === 'calculus introduction' ? '/w/ws/d/doc1' : null;
		const html = renderInline('See [[Calculus Introduction]] and [[Missing]]', resolve);
		expect(html).toContain('<a class="wikilink" href="/w/ws/d/doc1"');
		expect(html).toContain('>Calculus Introduction</a>');
		expect(html).toContain('class="wikilink broken"');
		expect(html).toContain('data-wikilink="Missing"');
	});

	it('escapes wikilink titles so they cannot inject HTML', () => {
		const html = renderInline('[[<script>evil</script>]]', () => null);
		expect(html).not.toContain('<script>');
		expect(html).toContain('&lt;script&gt;');
	});

	it('still renders single-dollar math inline (no display block)', () => {
		const html = renderInline('mass is $E = mc^2$ today');
		expect(html).toContain('katex');
		expect(html).not.toContain('katex-display');
	});
});
