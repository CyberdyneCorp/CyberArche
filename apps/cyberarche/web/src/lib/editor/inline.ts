/** Inline rich renderer (block-editor spec): turns a stored source string into
 * display HTML — inline math `$…$`, `**bold**`, `*italic*`/`_italic_`, inline
 * `` `code` ``, and `~~strikethrough~~`. Used by
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

/** Apply emphasis to an already-HTML-escaped fragment. Inline code is rendered
 * first so markers inside a code span are shown literally, not as emphasis. */
function renderEmphasis(escaped: string): string {
	return escaped
		.replace(/`([^`]+)`/g, '<code>$1</code>')
		.replace(/~~([^~]+)~~/g, '<del>$1</del>')
		.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
		.replace(/(^|[^*])\*([^*]+)\*(?!\*)/g, '$1<em>$2</em>')
		.replace(/(^|[^_])_([^_]+)_(?!_)/g, '$1<em>$2</em>');
}

function escapeAttr(text: string): string {
	return escapeHtml(text).replace(/"/g, '&quot;');
}

/** Resolve a wikilink title to an href, or null if no document matches. */
export type LinkResolver = (title: string) => string | null;

/** Only http(s)/mailto external links are rendered; anything else (javascript:,
 * data:, …) falls back to text so a cell can never inject a dangerous href. */
function safeHref(url: string): string | null {
	return /^(https?:\/\/|mailto:)/i.test(url.trim()) ? url.trim() : null;
}

/** Render a plain-text segment: `[[Title]]` wikilinks and `[label](url)`
 * external links become links; the rest gets HTML-escaped emphasis. */
function renderTextSegment(text: string, resolve?: LinkResolver): string {
	// Split on wikilinks OR markdown links, keeping the delimiters.
	return text
		.split(/(\[\[[^[\]]+\]\]|\[[^\][]+\]\([^\s()]+\))/g)
		.map((part) => {
			const wiki = /^\[\[([^[\]]+)\]\]$/.exec(part);
			if (wiki) {
				const title = wiki[1].trim();
				const label = escapeHtml(title);
				const href = resolve?.(title) ?? null;
				const attr = `data-wikilink="${escapeAttr(title)}" contenteditable="false"`;
				return href
					? `<a class="wikilink" href="${escapeAttr(href)}" ${attr}>${label}</a>`
					: `<span class="wikilink broken" ${attr}>${label}</span>`;
			}
			const md = /^\[([^\][]+)\]\(([^\s()]+)\)$/.exec(part);
			if (md) {
				const href = safeHref(md[2]);
				const label = renderEmphasis(escapeHtml(md[1].trim()));
				return href
					? `<a class="ext-link" href="${escapeAttr(href)}" target="_blank" ` +
							`rel="noopener noreferrer">${label}</a>`
					: renderEmphasis(escapeHtml(part));
			}
			return renderEmphasis(escapeHtml(part));
		})
		.join('');
}

/** Render `text` to display HTML. `$` is the math delimiter; `\$` is a literal.
 * TeX `\(…\)` and `\[…\]` delimiters are accepted too. `[[Title]]` renders as a
 * wikilink via `resolve`. */
export function renderInline(text: string, resolve?: LinkResolver): string {
	if (!text) return '';
	text = normalizeTexDelimiters(text);
	return tokenizeMath(text)
		.map((token) => {
			if (token.type === 'inline') return renderMath(token.value, false);
			if (token.type === 'display') return renderMath(token.value, true);
			return renderTextSegment(token.value, resolve);
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
