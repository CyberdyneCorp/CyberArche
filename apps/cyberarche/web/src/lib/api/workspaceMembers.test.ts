import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
	listWorkspaceMembers,
	removeWorkspaceMember,
	setWorkspaceMemberRole
} from './workspaceMembers';

/** Captures every request so each client's URL/method/body shape is asserted. */
function capturingFetch(body: unknown = null, status = 200) {
	const calls: Array<{ url: string; method: string; body: unknown }> = [];
	const fn = vi.fn(async (url: string, init?: RequestInit) => {
		calls.push({
			url,
			method: init?.method ?? 'GET',
			body: init?.body ? JSON.parse(String(init.body)) : undefined
		});
		return { ok: true, status, json: async () => body };
	}) as unknown as typeof fetch;
	return { fn, calls };
}

describe('workspaceMembers API client', () => {
	beforeEach(() => vi.restoreAllMocks());

	it('listWorkspaceMembers gets the workspace members', async () => {
		const member = {
			user_id: 'alice',
			role: 'owner',
			granted_at: '2026-01-01T00:00:00Z',
			email: 'alice@acme.dev',
			avatar_url: null
		};
		const { fn, calls } = capturingFetch([member]);
		vi.stubGlobal('fetch', fn);

		expect(await listWorkspaceMembers('ws-1')).toEqual([member]);
		expect(calls).toEqual([
			{ url: '/api/v1/workspaces/ws-1/members', method: 'GET', body: undefined }
		]);
	});

	it('setWorkspaceMemberRole patches the member with the new role', async () => {
		const membership = { user_id: 'bob', role: 'viewer', granted_at: '2026-01-01T00:00:00Z' };
		const { fn, calls } = capturingFetch(membership);
		vi.stubGlobal('fetch', fn);

		expect(await setWorkspaceMemberRole('ws-1', 'bob', 'viewer')).toEqual(membership);
		expect(calls).toEqual([
			{
				url: '/api/v1/workspaces/ws-1/members/bob',
				method: 'PATCH',
				body: { role: 'viewer' }
			}
		]);
	});

	it('removeWorkspaceMember deletes the membership (204)', async () => {
		const { fn, calls } = capturingFetch(null, 204);
		vi.stubGlobal('fetch', fn);

		expect(await removeWorkspaceMember('ws-1', 'bob')).toBeUndefined();
		expect(calls).toEqual([
			{ url: '/api/v1/workspaces/ws-1/members/bob', method: 'DELETE', body: undefined }
		]);
	});
});
