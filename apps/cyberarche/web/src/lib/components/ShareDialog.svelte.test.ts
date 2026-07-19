import { flushSync, mount, unmount } from 'svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { SharingVM } from '$lib/viewmodels/sharing.svelte';

// The dialog spins up the org-directory view-model on mount; stub it so the
// component mounts in isolation without touching the network.
const orgUsersStub = vi.hoisted(() => ({ current: {} as Record<string, unknown> }));
vi.mock('$lib/viewmodels/orgUsers.svelte', () => ({
	createOrgUsers: () => orgUsersStub.current
}));

import ShareDialog from './ShareDialog.svelte';

const USER = (id: string, email: string | null = `${id}@acme.dev`) => ({
	id,
	email,
	avatar_url: null,
	is_active: true
});

function sharingStub() {
	return {
		documentId: 'doc-1',
		links: [],
		comments: [],
		error: null,
		invited: null,
		invite: vi.fn(),
		linkUrl: () => '',
		createLink: vi.fn(),
		revokeLink: vi.fn()
	} as unknown as SharingVM;
}

describe('ShareDialog invite picker', () => {
	let target: HTMLElement;
	let instance: Record<string, unknown> | null = null;

	beforeEach(() => {
		target = document.createElement('div');
		document.body.appendChild(target);
		orgUsersStub.current = {
			users: [],
			total: 0,
			loading: false,
			unavailable: false,
			error: null,
			load: vi.fn(),
			search: vi.fn()
		};
	});
	afterEach(() => {
		if (instance) unmount(instance);
		instance = null;
		target.remove();
		vi.clearAllMocks();
	});

	function render(sharing: SharingVM) {
		instance = mount(ShareDialog, { target, props: { sharing, onclose: vi.fn() } });
		flushSync();
	}

	function input(): HTMLInputElement {
		return target.querySelector<HTMLInputElement>('[data-testid="invite-user"]')!;
	}

	function type(value: string) {
		const field = input();
		field.value = value;
		field.dispatchEvent(new Event('input', { bubbles: true }));
		flushSync();
	}

	function submitInvite() {
		input().closest('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
		flushSync();
	}

	it('searches the directory as you type and invites the picked user', () => {
		orgUsersStub.current.users = [USER('u-ada', 'ada@acme.dev'), USER('u-bob', 'bob@acme.dev')];
		const sharing = sharingStub();
		render(sharing);

		expect(input().getAttribute('role')).toBe('combobox');
		type('ada');
		expect(orgUsersStub.current.search).toHaveBeenCalledWith('ada');

		const options = target.querySelectorAll<HTMLButtonElement>(
			'[data-testid="invite-user-option"]'
		);
		expect(options).toHaveLength(2);
		expect(options[0].textContent).toContain('ada@acme.dev');
		options[0].click();
		flushSync();
		expect(input().value).toBe('ada@acme.dev');

		submitInvite();
		expect(sharing.invite).toHaveBeenCalledWith('u-ada', 'editor');
	});

	it('selecting with the keyboard fills the invite target', () => {
		orgUsersStub.current.users = [USER('u-ada'), USER('u-bob')];
		const sharing = sharingStub();
		render(sharing);

		type('a');
		const field = input();
		field.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
		field.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
		flushSync();

		submitInvite();
		expect(sharing.invite).toHaveBeenCalledWith('u-bob', 'editor');
	});

	it('falls back to raw-id entry when the directory is unavailable', () => {
		orgUsersStub.current.unavailable = true;
		const sharing = sharingStub();
		render(sharing);

		expect(input().placeholder).toContain('User id');
		type('raw-user-1');
		submitInvite();

		expect(sharing.invite).toHaveBeenCalledWith('raw-user-1', 'editor');
		// No way back to the picker while the directory is down.
		expect(target.querySelector('[data-testid="invite-user-search-directory"]')).toBeNull();
	});

	it('lets an org user switch to manual id entry and back', () => {
		orgUsersStub.current.users = [USER('u-ada')];
		const sharing = sharingStub();
		render(sharing);

		target
			.querySelector<HTMLButtonElement>('[data-testid="invite-user-manual"]')!
			.click();
		flushSync();
		expect(input().placeholder).toContain('User id');

		type('raw-user-2');
		submitInvite();
		expect(sharing.invite).toHaveBeenCalledWith('raw-user-2', 'editor');

		target
			.querySelector<HTMLButtonElement>('[data-testid="invite-user-search-directory"]')!
			.click();
		flushSync();
		expect(input().getAttribute('role')).toBe('combobox');
	});

	it('does not invite without a selected target', () => {
		orgUsersStub.current.users = [USER('u-ada')];
		const sharing = sharingStub();
		render(sharing);

		type('ada');
		submitInvite();

		expect(sharing.invite).not.toHaveBeenCalled();
	});
});
