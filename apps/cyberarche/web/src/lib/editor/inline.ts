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

function renderMath(source: string): string {
	try {
		return katex.renderToString(source, { displayMode: false, throwOnError: true });
	} catch (error) {
		const message = escapeHtml(error instanceof Error ? error.message : 'invalid math');
		// Non-destructive: show the raw source flagged, never drop it.
		return `<span class="inline-math-error" title="${message}">$${escapeHtml(source)}$</span>`;
	}
}

/** Apply emphasis to an already-HTML-escaped fragment. */
function renderEmphasis(escaped: string): string {
	return escaped
		.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
		.replace(/(^|[^*])\*([^*]+)\*(?!\*)/g, '$1<em>$2</em>')
		.replace(/(^|[^_])_([^_]+)_(?!_)/g, '$1<em>$2</em>');
}

/** Render `text` to display HTML. `$` is the math delimiter; `\$` is a literal. */
export function renderInline(text: string): string {
	if (!text) return '';
	// Split on unescaped `$…$` pairs. Even indices are plain text, odd are math.
	const parts = splitMath(text);
	return parts
		.map((part, index) =>
			index % 2 === 1 ? renderMath(part) : renderEmphasis(escapeHtml(part))
		)
		.join('')
		.replace(/\\\$/g, '$'); // unescape literal dollars in the plain segments
}

/** ['before', 'math', 'between', 'math', 'after'] — odd slots are math bodies.
 * A `$` preceded by a backslash is literal and does not open/close math. */
function splitMath(text: string): string[] {
	const parts: string[] = [];
	let buffer = '';
	let mathBody: string | null = null;
	for (let i = 0; i < text.length; i++) {
		const char = text[i];
		const escaped = i > 0 && text[i - 1] === '\\';
		if (char === '$' && !escaped) {
			if (mathBody === null) {
				parts.push(buffer);
				buffer = '';
				mathBody = '';
			} else {
				parts.push(mathBody);
				mathBody = null;
			}
			continue;
		}
		if (mathBody === null) buffer += char;
		else mathBody += char;
	}
	// An unclosed `$` is not math — fold it back into the trailing text.
	if (mathBody !== null) parts[parts.length - 1] += '$' + mathBody;
	else parts.push(buffer);
	return parts;
}
