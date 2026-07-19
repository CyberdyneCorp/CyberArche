import { flushSync, mount, unmount } from 'svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('$app/navigation', () => ({ goto: vi.fn() }));
vi.mock('$lib/api/notifications', () => ({
	notificationsUnreadCount: vi.fn(async () => ({ count: 3 })),
	listNotifications: vi.fn(async () => []),
	markNotificationRead: vi.fn(async () => {}),
	markAllNotificationsRead: vi.fn(async () => {})
}));

import NotificationsBell from './NotificationsBell.svelte';

describe('NotificationsBell component', () => {
	let target: HTMLElement;
	let instance: Record<string, unknown> | null = null;

	beforeEach(() => {
		target = document.createElement('div');
		document.body.appendChild(target);
	});
	afterEach(() => {
		if (instance) unmount(instance);
		instance = null;
		target.remove();
		vi.clearAllMocks();
	});

	function render(props: Record<string, unknown>) {
		instance = mount(NotificationsBell, { target, props: props as never });
		flushSync();
	}

	it('renders the nav variant as a labeled row with an unread count badge', async () => {
		render({ workspaceId: 'ws-1', variant: 'nav' });

		const trigger = target.querySelector<HTMLButtonElement>(
			'[data-testid="notifications-bell"]'
		);
		expect(trigger).not.toBeNull();
		expect(trigger!.classList.contains('nav-row')).toBe(true);
		expect(trigger!.textContent).toContain('Notifications');

		// The unread count is polled on mount; wait for the badge to reflect it.
		await vi.waitFor(() => {
			flushSync();
			const badge = target.querySelector('[data-testid="notifications-badge"]');
			expect(badge?.textContent).toBe('3');
		});
	});

	it('opens the panel downward when triggered from the nav', async () => {
		render({ workspaceId: 'ws-1', variant: 'nav' });
		target.querySelector<HTMLButtonElement>('[data-testid="notifications-bell"]')!.click();
		flushSync();

		const pop = target.querySelector('[data-testid="notifications-pop"]');
		expect(pop).not.toBeNull();
		expect(pop!.classList.contains('pop-down')).toBe(true);
	});
});
