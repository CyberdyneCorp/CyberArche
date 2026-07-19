/** Workspace members ViewModel (workspace-members spec): list memberships,
 * invite, change roles, remove — with owner gating derived from the session
 * user and last-owner conflicts mapped to a friendly message. */

import { ApiError } from '$lib/api/http';
import { inviteToWorkspace, type ShareRole } from '$lib/api/sharing';
import {
	listWorkspaceMembers,
	removeWorkspaceMember,
	setWorkspaceMemberRole,
	type WorkspaceMember
} from '$lib/api/workspaceMembers';
import { session } from '$lib/viewmodels/session.svelte';

function friendlyMessage(err: unknown): string {
	if (err instanceof ApiError) {
		if (err.status === 409) return 'A workspace must keep at least one owner.';
		if (err.status === 403) return 'Only workspace owners can manage members.';
	}
	return (err as Error).message;
}

export function createWorkspaceMembers(workspaceId: string) {
	let members = $state<WorkspaceMember[]>([]);
	let loading = $state(false);
	let busy = $state(false);
	let error = $state<string | null>(null);

	async function guard<T>(action: () => Promise<T>): Promise<boolean> {
		error = null;
		busy = true;
		try {
			await action();
			return true;
		} catch (err) {
			error = friendlyMessage(err);
			return false;
		} finally {
			busy = false;
		}
	}

	return {
		workspaceId,
		get members() {
			return members;
		},
		get loading() {
			return loading;
		},
		get busy() {
			return busy;
		},
		get error() {
			return error;
		},
		get myRole(): ShareRole | null {
			return members.find((m) => m.user_id === session.userId)?.role ?? null;
		},
		get isOwner() {
			return this.myRole === 'owner';
		},

		async load(): Promise<void> {
			loading = true;
			try {
				members = await listWorkspaceMembers(workspaceId);
				error = null;
			} catch (err) {
				error = friendlyMessage(err);
			} finally {
				loading = false;
			}
		},

		async invite(userId: string, role: ShareRole): Promise<boolean> {
			const ok = await guard(() => inviteToWorkspace(workspaceId, userId, role));
			if (ok) await this.load();
			return ok;
		},

		async setRole(userId: string, role: ShareRole): Promise<boolean> {
			return guard(async () => {
				const updated = await setWorkspaceMemberRole(workspaceId, userId, role);
				members = members.map((m) =>
					m.user_id === userId ? { ...m, role: updated.role } : m
				);
			});
		},

		async remove(userId: string): Promise<boolean> {
			return guard(async () => {
				await removeWorkspaceMember(workspaceId, userId);
				members = members.filter((m) => m.user_id !== userId);
			});
		}
	};
}

export type WorkspaceMembersVM = ReturnType<typeof createWorkspaceMembers>;
