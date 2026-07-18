import { existsSync, readFileSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

// src/lib/ -> ../../static
const STATIC = resolve(dirname(fileURLToPath(import.meta.url)), '../../static');

describe('PWA manifest', () => {
	const raw = readFileSync(resolve(STATIC, 'manifest.webmanifest'), 'utf8');
	const manifest = JSON.parse(raw) as {
		name: string;
		start_url: string;
		display: string;
		icons: { src: string; sizes: string; purpose?: string }[];
	};

	it('parses as JSON with the core install fields', () => {
		expect(manifest.name).toBe('CyberArche');
		expect(manifest.start_url).toBe('/');
		expect(manifest.display).toBe('standalone');
	});

	it('declares 192 + 512 + maskable icons', () => {
		const has = (pred: (i: (typeof manifest.icons)[number]) => boolean) =>
			manifest.icons.some(pred);
		expect(has((i) => i.sizes === '192x192')).toBe(true);
		expect(has((i) => i.sizes === '512x512' && i.purpose !== 'maskable')).toBe(true);
		expect(has((i) => i.sizes === '512x512' && i.purpose === 'maskable')).toBe(true);
	});

	it('references icon files that exist and are non-empty on disk', () => {
		for (const icon of manifest.icons) {
			const path = resolve(STATIC, icon.src.replace(/^\//, ''));
			expect(existsSync(path), `${icon.src} exists`).toBe(true);
			expect(statSync(path).size, `${icon.src} non-empty`).toBeGreaterThan(0);
		}
	});
});

describe('PWA icon assets', () => {
	const icons = [
		'icons/icon-192.png',
		'icons/icon-512.png',
		'icons/icon-maskable-512.png',
		'icons/apple-touch-icon.png',
		'icons/favicon.png'
	];
	for (const rel of icons) {
		it(`${rel} exists and is non-empty`, () => {
			const path = resolve(STATIC, rel);
			expect(existsSync(path)).toBe(true);
			expect(statSync(path).size).toBeGreaterThan(0);
		});
	}
});
