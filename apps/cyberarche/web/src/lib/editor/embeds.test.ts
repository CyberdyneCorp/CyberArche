import { describe, expect, it } from 'vitest';

import { parseEmbed } from './embeds';

describe('parseEmbed', () => {
	it('maps YouTube watch/shorts/youtu.be to the embed player', () => {
		expect(parseEmbed('https://www.youtube.com/watch?v=dQw4w9WgXcQ')).toEqual({
			provider: 'youtube',
			embedUrl: 'https://www.youtube.com/embed/dQw4w9WgXcQ'
		});
		expect(parseEmbed('https://youtu.be/dQw4w9WgXcQ')?.embedUrl).toBe(
			'https://www.youtube.com/embed/dQw4w9WgXcQ'
		);
		expect(parseEmbed('https://youtube.com/shorts/abc123')?.embedUrl).toBe(
			'https://www.youtube.com/embed/abc123'
		);
	});

	it('maps Vimeo and Loom to their players', () => {
		expect(parseEmbed('https://vimeo.com/123456789')).toEqual({
			provider: 'vimeo',
			embedUrl: 'https://player.vimeo.com/video/123456789'
		});
		expect(parseEmbed('https://www.loom.com/share/abcDEF123')).toEqual({
			provider: 'loom',
			embedUrl: 'https://www.loom.com/embed/abcDEF123'
		});
	});

	it('treats any other https URL as a generic iframe', () => {
		expect(parseEmbed('https://example.com/page')).toEqual({
			provider: 'iframe',
			embedUrl: 'https://example.com/page'
		});
	});

	it('refuses non-https and unparseable URLs', () => {
		expect(parseEmbed('http://example.com')).toBeNull();
		expect(parseEmbed('javascript:alert(1)')).toBeNull();
		expect(parseEmbed('not a url')).toBeNull();
		expect(parseEmbed('')).toBeNull();
	});
});
