import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
	listNotifications,
	markAllNotificationsRead,
	markNotificationRead,
	notificationsUnreadCount,
	type AppNotification
} from './notifications';

const NOTIFICATION: AppNotification = {
	id: 'n-1',
	kind: 'mention',
	actor_id: 'alice',
	document_id: 'doc-1',
	comment_id: null,
	snippet: '@you look at this',
	read: false,
	created_at: '2026-01-01T00:00:00Z'
};

function mockFetch(body: unknown) {
	return vi.fn(async () => ({
		ok: true,
		status: 200,
		json: async () => body
	})) as unknown as typeof fetch;
}

describe('notifications API client', () => {
	beforeEach(() => vi.restoreAllMocks());

	it('listNotifications GETs the inbox', async () => {
		const fetchMock = mockFetch([NOTIFICATION]);
		vi.stubGlobal('fetch', fetchMock);

		expect(await listNotifications()).toEqual([NOTIFICATION]);

		const [url, init] = (fetchMock as ReturnType<typeof vi.fn>).mock.calls[0];
		expect(url).toBe('/api/v1/notifications');
		expect(init?.method).toBeUndefined(); // GET
	});

	it('notificationsUnreadCount GETs the unread counter', async () => {
		const fetchMock = mockFetch({ count: 3 });
		vi.stubGlobal('fetch', fetchMock);

		expect(await notificationsUnreadCount()).toEqual({ count: 3 });

		const [url] = (fetchMock as ReturnType<typeof vi.fn>).mock.calls[0];
		expect(url).toBe('/api/v1/notifications/unread-count');
	});

	it('markNotificationRead POSTs to the notification id', async () => {
		const fetchMock = mockFetch(null);
		vi.stubGlobal('fetch', fetchMock);

		await markNotificationRead('n-1');

		const [url, init] = (fetchMock as ReturnType<typeof vi.fn>).mock.calls[0];
		expect(url).toBe('/api/v1/notifications/n-1/read');
		expect(init?.method).toBe('POST');
		expect(init?.body).toBe('{}');
	});

	it('markAllNotificationsRead POSTs read-all', async () => {
		const fetchMock = mockFetch(null);
		vi.stubGlobal('fetch', fetchMock);

		await markAllNotificationsRead();

		const [url, init] = (fetchMock as ReturnType<typeof vi.fn>).mock.calls[0];
		expect(url).toBe('/api/v1/notifications/read-all');
		expect(init?.method).toBe('POST');
		expect(init?.body).toBe('{}');
	});

	it('surfaces API errors from the http core', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async () => ({
				ok: false,
				status: 403,
				json: async () => ({ detail: 'forbidden' })
			})) as unknown as typeof fetch
		);

		await expect(listNotifications()).rejects.toThrow(/403.*forbidden/);
	});
});
