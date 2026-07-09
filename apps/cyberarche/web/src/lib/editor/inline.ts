/** Inline rich renderer (block-editor spec): turns a stored source string into
 * display HTML — inline math `$…$`, `**bold**`, `*italic*`/`_italic_`. Used by
 * paragraph/heading text and table cells when they are NOT being edited; the
 * raw source is shown for editing and stored verbatim, so this is display-only
 * and never mutates content.
 *
 * Order matters: escape first (so user text can never inject HTML), then math
 * (KaTeX emits its own trusted markup), then emphasis on the remaining text. */

import katex from 'katex';

function escapeHtml(text: string): string {
	return text
		.replace(/&/g, '&amp;')
		.replace(/</g, '&lt;')
		.replace(/>/g, '&gt;');
}

function renderMath(source: string, displayMode: boolean): string {
	try {
		return katex.renderToString(source, { displayMode, throwOnError: true });
	} catch (error) {
		const message = escapeHtml(error instanceof Error ? error.message : 'invalid math');
		// Non-destructive: show the raw source flagged, never drop it.
		const fence = displayMode ? '$$' : '$';
		return `<span class="inline-math-error" title="${message}">${fence}${escapeHtml(source)}${fence}</span>`;
	}
}

/** Apply emphasis to an already-HTML-escaped fragment. */
function renderEmphasis(escaped: string): string {
	return escaped
		.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
		.replace(/(^|[^*])\*([^*]+)\*(?!\*)/g, '$1<em>$2</em>')
		.replace(/(^|[^_])_([^_]+)_(?!_)/g, '$1<em>$2</em>');
}

/** Render `text` to display HTML. `$` is the math delimiter; `\$` is a literal.
 * TeX `\(…\)` and `\[…\]` delimiters are accepted too, so content the agent (or
 * a paste) wrote in that form still typesets. */
export function renderInline(text: string): string {
	if (!text) return '';
	text = normalizeTexDelimiters(text);
	return tokenizeMath(text)
		.map((token) => {
			if (token.type === 'inline') return renderMath(token.value, false);
			if (token.type === 'display') return renderMath(token.value, true);
			return renderEmphasis(escapeHtml(token.value));
		})
		.join('')
		.replace(/\\\$/g, '$'); // unescape literal dollars in the plain segments
}

/** Rewrite TeX delimiters so one tokenizer handles every form: `\(…\)` → inline
 * `$…$`, `\[…\]` → display `$$…$$`. */
function normalizeTexDelimiters(text: string): string {
	return text
		.replace(/\\\[(.+?)\\\]/gs, (_, body) => `$$${body.trim()}$$`)
		.replace(/\\\((.+?)\\\)/gs, (_, body) => `$${body.trim()}$`);
}

interface MathToken {
	type: 'text' | 'inline' | 'display';
	value: string;
}

/** Split text into plain / inline `$…$` / display `$$…$$` segments. A `$`
 * preceded by a backslash is literal; an unclosed delimiter folds back into
 * text. `$$` is matched before `$`, so display math is not read as two empty
 * inline spans (the bug that showed `$$\nabla$$` as raw source). */
function tokenizeMath(text: string): MathToken[] {
	const tokens: MathToken[] = [];
	let buffer = '';
	let i = 0;
	const flush = () => {
		if (buffer) tokens.push({ type: 'text', value: buffer });
		buffer = '';
	};
	while (i < text.length) {
		const unescaped = text[i] === '$' && text[i - 1] !== '\\';
		if (unescaped && text[i + 1] === '$') {
			const end = text.indexOf('$$', i + 2);
			if (end !== -1) {
				flush();
				tokens.push({ type: 'display', value: text.slice(i + 2, end).trim() });
				i = end + 2;
				continue;
			}
		} else if (unescaped) {
			const end = findInlineClose(text, i + 1);
			if (end !== -1) {
				flush();
				tokens.push({ type: 'inline', value: text.slice(i + 1, end) });
				i = end + 1;
				continue;
			}
		}
		buffer += text[i];
		i++;
	}
	flush();
	return tokens;
}

function findInlineClose(text: string, from: number): number {
	for (let j = from; j < text.length; j++) {
		if (text[j] === '$' && text[j - 1] !== '\\') return j;
	}
	return -1;
}
