/** Parse a media URL into an embeddable player URL (block-editor spec).
 *
 * YouTube / Vimeo / Loom get canonical player URLs; any other https URL is
 * returned as a generic iframe target. Non-https (and unparseable) URLs return
 * null so the block refuses to embed them. */

export interface ParsedEmbed {
	provider: 'youtube' | 'vimeo' | 'loom' | 'iframe';
	embedUrl: string;
}

export function parseEmbed(raw: string): ParsedEmbed | null {
	const value = (raw ?? '').trim();
	if (!value) return null;
	let url: URL;
	try {
		url = new URL(value);
	} catch {
		return null;
	}
	if (url.protocol !== 'https:') return null;
	const host = url.hostname.replace(/^www\./, '');

	if (host === 'youtube.com' || host === 'm.youtube.com') {
		const v = url.searchParams.get('v');
		if (v) return { provider: 'youtube', embedUrl: `https://www.youtube.com/embed/${v}` };
		const path = url.pathname.match(/^\/(?:embed|shorts|live)\/([\w-]+)/);
		if (path) return { provider: 'youtube', embedUrl: `https://www.youtube.com/embed/${path[1]}` };
	}
	if (host === 'youtu.be') {
		const id = url.pathname.slice(1).split('/')[0];
		if (id) return { provider: 'youtube', embedUrl: `https://www.youtube.com/embed/${id}` };
	}
	if (host === 'vimeo.com' || host === 'player.vimeo.com') {
		const id = url.pathname.split('/').filter(Boolean).pop();
		if (id && /^\d+$/.test(id)) {
			return { provider: 'vimeo', embedUrl: `https://player.vimeo.com/video/${id}` };
		}
	}
	if (host === 'loom.com') {
		const share = url.pathname.match(/^\/(?:share|embed)\/([\w-]+)/);
		if (share) return { provider: 'loom', embedUrl: `https://www.loom.com/embed/${share[1]}` };
	}

	// Any other https URL: embed in a sandboxed iframe (the component sandboxes it).
	return { provider: 'iframe', embedUrl: value };
}
