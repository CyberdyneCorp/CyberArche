import { flushSync, mount, unmount } from 'svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// The modal spins up every workspace view-model in an effect; stub them all so
// the component mounts in isolation without touching the network.
const stub = (extra: Record<string, unknown> = {}) => ({ load: vi.fn(), ...extra });

vi.mock('$app/state', () => ({ page: { url: new URL('http://localhost:5173/') } }));
vi.mock('$lib/viewmodels/api-keys.svelte', () => ({
	createApiKeys: () => stub({ items: [], justCreated: null, error: null })
}));
vi.mock('$lib/viewmodels/connectors.svelte', () => ({
	createConnectors: () => stub({ items: [], busy: false, error: null, toolsOf: () => [] })
}));
vi.mock('$lib/viewmodels/agentPersona.svelte', () => ({
	createAgentPersona: () =>
		stub({ workspaceText: '', personalText: '', memories: [], busy: false, error: null })
}));
vi.mock('$lib/viewmodels/agentSkills.svelte', () => ({
	createAgentSkills: () => stub({ skills: [], busy: false, error: null })
}));
vi.mock('$lib/viewmodels/scheduledAgents.svelte', () => ({
	createScheduledAgents: () => stub({ tasks: [], busy: false, error: null })
}));
vi.mock('$lib/viewmodels/google.svelte', () => ({
	createGoogle: () => stub({ status: null, error: null }),
	GOOGLE_GROUPS: []
}));
vi.mock('$lib/viewmodels/notificationPrefs.svelte', () => ({
	createNotificationPrefs: () => stub({ prefs: {}, busy: false, error: null })
}));

import { theme } from '$lib/viewmodels/theme.svelte';
import SettingsModal from './SettingsModal.svelte';

describe('SettingsModal — Appearance tab', () => {
	let target: HTMLElement;
	let instance: Record<string, unknown> | null = null;

	beforeEach(() => {
		target = document.createElement('div');
		document.body.appendChild(target);
		localStorage.clear();
		delete document.documentElement.dataset.theme;
	});
	afterEach(() => {
		if (instance) unmount(instance);
		instance = null;
		target.remove();
		vi.clearAllMocks();
	});

	function render() {
		instance = mount(SettingsModal, { target, props: { workspaceId: 'ws-1' } });
		flushSync();
	}

	it('switches the theme when a theme option is chosen', () => {
		render();
		const setSpy = vi.spyOn(theme, 'set');

		// Open the Appearance tab.
		target.querySelector<HTMLButtonElement>('[data-testid="settings-tab-appearance"]')!.click();
		flushSync();

		const pane = target.querySelector('[data-testid="settings-tab-appearance"]');
		expect(pane).not.toBeNull();

		// Choose Dark.
		target.querySelector<HTMLButtonElement>('[data-testid="theme-option-dark"]')!.click();
		flushSync();

		expect(setSpy).toHaveBeenCalledWith('dark');
		expect(theme.mode).toBe('dark');

		// The selected option is reflected in the UI.
		const darkOption = target.querySelector('[data-testid="theme-option-dark"]')!;
		expect(darkOption.getAttribute('aria-checked')).toBe('true');

		setSpy.mockRestore();
	});
});
