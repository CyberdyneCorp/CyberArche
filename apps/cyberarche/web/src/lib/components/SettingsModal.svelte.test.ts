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
const memberStubs = vi.hoisted(() => ({
	members: {} as Record<string, unknown>,
	orgUsers: {} as Record<string, unknown>
}));
vi.mock('$lib/viewmodels/workspaceMembers.svelte', () => ({
	createWorkspaceMembers: () => memberStubs.members
}));
vi.mock('$lib/viewmodels/orgUsers.svelte', () => ({
	createOrgUsers: () => memberStubs.orgUsers
}));

import { theme } from '$lib/viewmodels/theme.svelte';
import SettingsModal from './SettingsModal.svelte';

const MEMBER = (user_id: string, role: string, email: string | null = `${user_id}@acme.dev`) => ({
	user_id,
	role,
	granted_at: '2026-01-01T00:00:00Z',
	email,
	avatar_url: null
});

describe('SettingsModal', () => {
	let target: HTMLElement;
	let instance: Record<string, unknown> | null = null;

	beforeEach(() => {
		target = document.createElement('div');
		document.body.appendChild(target);
		localStorage.clear();
		delete document.documentElement.dataset.theme;
		memberStubs.members = stub({
			members: [],
			loading: false,
			busy: false,
			error: null,
			myRole: null,
			isOwner: false,
			invite: vi.fn(),
			setRole: vi.fn(),
			remove: vi.fn()
		});
		memberStubs.orgUsers = stub({
			users: [],
			total: 0,
			loading: false,
			unavailable: false,
			error: null,
			search: vi.fn()
		});
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

	function openMembersTab() {
		render();
		target.querySelector<HTMLButtonElement>('[data-testid="settings-tab-members"]')!.click();
		flushSync();
	}

	it('members tab lists members with owner-only role and remove controls', () => {
		memberStubs.members = stub({
			members: [MEMBER('alice', 'owner'), MEMBER('bob', 'editor', null)],
			loading: false,
			busy: false,
			error: null,
			myRole: 'owner',
			isOwner: true,
			invite: vi.fn(),
			setRole: vi.fn(),
			remove: vi.fn()
		});
		openMembersTab();

		const rows = target.querySelectorAll('[data-testid="member-row"]');
		expect(rows).toHaveLength(2);
		// Email when the directory enriched it, bare user id otherwise.
		expect(rows[0].textContent).toContain('alice@acme.dev');
		expect(rows[1].textContent).toContain('bob');
		expect(target.querySelectorAll('[data-testid="member-role"]')).toHaveLength(2);
		expect(target.querySelectorAll('[data-testid="member-remove"]')).toHaveLength(2);
	});

	it('members tab hides role and remove controls from non-owners', () => {
		memberStubs.members = stub({
			members: [MEMBER('alice', 'viewer'), MEMBER('bob', 'owner')],
			loading: false,
			busy: false,
			error: null,
			myRole: 'viewer',
			isOwner: false,
			invite: vi.fn(),
			setRole: vi.fn(),
			remove: vi.fn()
		});
		openMembersTab();

		expect(target.querySelectorAll('[data-testid="member-row"]')).toHaveLength(2);
		expect(target.querySelectorAll('[data-testid="member-role"]')).toHaveLength(0);
		expect(target.querySelectorAll('[data-testid="member-remove"]')).toHaveLength(0);
	});

	it('members tab filters the list and surfaces errors inline', async () => {
		memberStubs.members = stub({
			members: [MEMBER('alice', 'owner'), MEMBER('bob', 'editor')],
			loading: false,
			busy: false,
			error: 'A workspace must keep at least one owner.',
			myRole: 'owner',
			isOwner: true,
			invite: vi.fn(),
			setRole: vi.fn(),
			remove: vi.fn()
		});
		openMembersTab();

		const search = target.querySelector<HTMLInputElement>('[data-testid="member-search"]')!;
		search.value = 'alice';
		search.dispatchEvent(new Event('input', { bubbles: true }));
		flushSync();

		const rows = target.querySelectorAll('[data-testid="member-row"]');
		expect(rows).toHaveLength(1);
		expect(rows[0].textContent).toContain('alice@acme.dev');
		expect(target.querySelector('[data-testid="members-error"]')!.textContent).toContain(
			'at least one owner'
		);
	});

	it('members tab restores the role select when the change is rejected', async () => {
		memberStubs.members = stub({
			members: [MEMBER('alice', 'owner')],
			loading: false,
			busy: false,
			error: null,
			myRole: 'owner',
			isOwner: true,
			invite: vi.fn(),
			setRole: vi.fn().mockResolvedValue(false), // e.g. last-owner 409
			remove: vi.fn()
		});
		openMembersTab();

		const select = target.querySelector<HTMLSelectElement>('[data-testid="member-role"]')!;
		expect(select.value).toBe('owner');
		select.value = 'editor';
		select.dispatchEvent(new Event('change', { bubbles: true }));
		await Promise.resolve();
		await Promise.resolve();
		flushSync();

		expect(memberStubs.members!.setRole).toHaveBeenCalledWith('alice', 'editor');
		expect(select.value).toBe('owner');
	});
});
