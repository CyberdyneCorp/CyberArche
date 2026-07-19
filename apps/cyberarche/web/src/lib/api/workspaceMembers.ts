/** Workspace membership administration (workspace-members spec): list with
 * roles, change a member's role, remove a member. Email/avatar are enriched
 * from the org directory best-effort (null when it is down). */
import { del, get, patch } from './http';
import type { ShareRole } from './sharing';

export interface WorkspaceMember {
	user_id: string;
	role: ShareRole;
	granted_at: string;
	email: string | null;
	avatar_url: string | null;
}

/** PATCH responses carry the membership only — no directory enrichment. */
export type WorkspaceMembership = Pick<WorkspaceMember, 'user_id' | 'role' | 'granted_at'>;

export const listWorkspaceMembers = (workspaceId: string) =>
	get<WorkspaceMember[]>(`/api/v1/workspaces/${workspaceId}/members`);

export const setWorkspaceMemberRole = (workspaceId: string, userId: string, role: ShareRole) =>
	patch<WorkspaceMembership>(`/api/v1/workspaces/${workspaceId}/members/${userId}`, { role });

export const removeWorkspaceMember = (workspaceId: string, userId: string) =>
	del<void>(`/api/v1/workspaces/${workspaceId}/members/${userId}`);
