import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { createTheme } from './theme.svelte';

const STORAGE_KEY = 'cyberarche.theme';

describe('theme ViewModel', () => {
	beforeEach(() => {
		localStorage.clear();
		delete document.documentElement.dataset.theme;
	});
	afterEach(() => vi.unstubAllGlobals());

	it('defaults to light and leaves the root unthemed', () => {
		const theme = createTheme();

		expect(theme.mode).toBe('light');
		expect(document.documentElement.dataset.theme).toBeUndefined();
	});

	it('restores a persisted dark mode and applies it on creation', () => {
		localStorage.setItem(STORAGE_KEY, 'dark');

		const theme = createTheme();

		expect(theme.mode).toBe('dark');
		expect(document.documentElement.dataset.theme).toBe('dark');
	});

	it('treats any non-dark stored value as light', () => {
		localStorage.setItem(STORAGE_KEY, 'light');

		expect(createTheme().mode).toBe('light');
		expect(document.documentElement.dataset.theme).toBeUndefined();
	});

	it('toggle switches to dark, persists it and stamps the root', () => {
		const theme = createTheme();

		theme.toggle();

		expect(theme.mode).toBe('dark');
		expect(localStorage.getItem(STORAGE_KEY)).toBe('dark');
		expect(document.documentElement.dataset.theme).toBe('dark');
	});

	it('toggling back to light persists it and clears the root attribute', () => {
		localStorage.setItem(STORAGE_KEY, 'dark');
		const theme = createTheme();

		theme.toggle();

		expect(theme.mode).toBe('light');
		expect(localStorage.getItem(STORAGE_KEY)).toBe('light');
		expect(document.documentElement.dataset.theme).toBeUndefined();
	});

	it('set(dark) switches, persists and stamps the root; set(light) reverts', () => {
		const theme = createTheme();

		theme.set('dark');
		expect(theme.mode).toBe('dark');
		expect(localStorage.getItem(STORAGE_KEY)).toBe('dark');
		expect(document.documentElement.dataset.theme).toBe('dark');

		theme.set('light');
		expect(theme.mode).toBe('light');
		expect(localStorage.getItem(STORAGE_KEY)).toBe('light');
		expect(document.documentElement.dataset.theme).toBeUndefined();
	});

	it('set() to the current mode is a no-op (no redundant write)', () => {
		const theme = createTheme();
		const spy = vi.spyOn(Storage.prototype, 'setItem');

		theme.set('light');

		expect(theme.mode).toBe('light');
		expect(spy).not.toHaveBeenCalled();
		spy.mockRestore();
	});

	it('falls back to light when localStorage is unavailable (SSR)', () => {
		vi.stubGlobal('localStorage', undefined);

		expect(createTheme().mode).toBe('light');
	});

	it('skips DOM application when document is unavailable (SSR)', () => {
		vi.stubGlobal('document', undefined);

		expect(() => createTheme()).not.toThrow();
	});
});
