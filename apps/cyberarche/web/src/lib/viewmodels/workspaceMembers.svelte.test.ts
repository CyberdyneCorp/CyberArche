import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('$lib/viewmodels/session.svelte', () => ({ session: { userId: 'alice' } }));

import { createWorkspaceMembers } from './workspaceMembers.svelte';

const MEMBER = (user_id: string, role = 'editor', email: string | null = `${user_id}@acme.dev`) => ({
	user_id,
	role,
	granted_at: '2026-01-01T00:00:00Z',
	email,
	avatar_url: null
});

type Route = { status?: number; body?: unknown };

/** Routes fetch by URL+method; a route may carry an error status. */
function routedFetch(routes: Record<string, Route>) {
	return vi.fn(async (url: string, init?: RequestInit) => {
		const key = `${init?.method ?? 'GET'} ${url}`;
		const route = routes[key];
		if (!route) throw new Error(`unrouted: ${key}`);
		const status = route.status ?? 200;
		return {
			ok: status < 400,
			status,
			json: async () => route.body ?? { error: 'Error', detail: 'nope' }
		};
	}) as unknown as typeof fetch;
}

const LIST = 'GET /api/v1/workspaces/ws-1/members';

describe('workspaceMembers ViewModel', () => {
	beforeEach(() => vi.restoreAllMocks());

	it('starts empty with no role for the session user', () => {
		const vm = createWorkspaceMembers('ws-1');

		expect(vm.workspaceId).toBe('ws-1');
		expect(vm.members).toEqual([]);
		expect(vm.myRole).toBeNull();
		expect(vm.isOwner).toBe(false);
		expect(vm.error).toBeNull();
	});

	it('load populates members and derives myRole/isOwner from the session user', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({ [LIST]: { body: [MEMBER('alice', 'owner'), MEMBER('bob')] } })
		);
		const vm = createWorkspaceMembers('ws-1');
		await vm.load();

		expect(vm.members.map((m) => m.user_id)).toEqual(['alice', 'bob']);
		expect(vm.myRole).toBe('owner');
		expect(vm.isOwner).toBe(true);
	});

	it('isOwner is false when the session user holds a lesser role', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({ [LIST]: { body: [MEMBER('alice', 'viewer'), MEMBER('bob', 'owner')] } })
		);
		const vm = createWorkspaceMembers('ws-1');
		await vm.load();

		expect(vm.myRole).toBe('viewer');
		expect(vm.isOwner).toBe(false);
	});

	it('a denied load (non-member 403) surfaces an error', async () => {
		vi.stubGlobal('fetch', routedFetch({ [LIST]: { status: 403 } }));
		const vm = createWorkspaceMembers('ws-1');
		await vm.load();

		expect(vm.members).toEqual([]);
		expect(vm.error).toMatch(/owners/i);
	});

	it('invite posts to the invites endpoint and reloads the list', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				'POST /api/v1/workspaces/ws-1/invites': { body: {} },
				[LIST]: { body: [MEMBER('alice', 'owner'), MEMBER('carol', 'viewer')] }
			})
		);
		const vm = createWorkspaceMembers('ws-1');

		expect(await vm.invite('carol', 'viewer')).toBe(true);
		expect(vm.members.map((m) => m.user_id)).toEqual(['alice', 'carol']);
		expect(vm.error).toBeNull();
	});

	it('a denied invite surfaces the owners-only message', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({ 'POST /api/v1/workspaces/ws-1/invites': { status: 403 } })
		);
		const vm = createWorkspaceMembers('ws-1');

		expect(await vm.invite('carol', 'viewer')).toBe(false);
		expect(vm.error).toBe('Only workspace owners can manage members.');
	});

	it('setRole patches the member and merges the new role locally', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				[LIST]: { body: [MEMBER('alice', 'owner'), MEMBER('bob', 'editor')] },
				'PATCH /api/v1/workspaces/ws-1/members/bob': {
					body: { user_id: 'bob', role: 'commenter', granted_at: '2026-01-01T00:00:00Z' }
				}
			})
		);
		const vm = createWorkspaceMembers('ws-1');
		await vm.load();

		expect(await vm.setRole('bob', 'commenter')).toBe(true);
		const bob = vm.members.find((m) => m.user_id === 'bob')!;
		expect(bob.role).toBe('commenter');
		// Directory enrichment is preserved — the PATCH body carries none.
		expect(bob.email).toBe('bob@acme.dev');
	});

	it('a 409 on setRole maps to the friendly last-owner message', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				[LIST]: { body: [MEMBER('alice', 'owner')] },
				'PATCH /api/v1/workspaces/ws-1/members/alice': {
					status: 409,
					body: { error: 'Conflict', detail: 'last owner' }
				}
			})
		);
		const vm = createWorkspaceMembers('ws-1');
		await vm.load();

		expect(await vm.setRole('alice', 'editor')).toBe(false);
		expect(vm.error).toBe('A workspace must keep at least one owner.');
		expect(vm.members[0].role).toBe('owner');
	});

	it('remove deletes the membership and drops the row', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				[LIST]: { body: [MEMBER('alice', 'owner'), MEMBER('bob')] },
				'DELETE /api/v1/workspaces/ws-1/members/bob': { status: 204, body: null }
			})
		);
		const vm = createWorkspaceMembers('ws-1');
		await vm.load();

		expect(await vm.remove('bob')).toBe(true);
		expect(vm.members.map((m) => m.user_id)).toEqual(['alice']);
	});

	it('a 409 on remove keeps the member and maps to the friendly message', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({
				[LIST]: { body: [MEMBER('alice', 'owner')] },
				'DELETE /api/v1/workspaces/ws-1/members/alice': {
					status: 409,
					body: { error: 'Conflict', detail: 'last owner' }
				}
			})
		);
		const vm = createWorkspaceMembers('ws-1');
		await vm.load();

		expect(await vm.remove('alice')).toBe(false);
		expect(vm.error).toBe('A workspace must keep at least one owner.');
		expect(vm.members).toHaveLength(1);
	});

	it('a successful action clears a previous error', async () => {
		vi.stubGlobal(
			'fetch',
			routedFetch({ 'POST /api/v1/workspaces/ws-1/invites': { status: 403 } })
		);
		const vm = createWorkspaceMembers('ws-1');
		await vm.invite('carol', 'viewer');
		expect(vm.error).not.toBeNull();

		vi.stubGlobal(
			'fetch',
			routedFetch({
				'POST /api/v1/workspaces/ws-1/invites': { body: {} },
				[LIST]: { body: [MEMBER('carol', 'viewer')] }
			})
		);
		await vm.invite('carol', 'viewer');

		expect(vm.error).toBeNull();
	});
});
