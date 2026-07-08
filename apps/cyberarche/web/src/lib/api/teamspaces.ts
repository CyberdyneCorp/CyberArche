import { del, get, post } from './http';
import type { Document } from './documents';
import type { ShareRole } from './sharing';

export interface Teamspace {
	id: string;
	workspace_id: string;
	name: string;
	icon: string;
	created_at: string;
}

export interface TeamspaceMember {
	user_id: string;
	role: ShareRole;
	granted_at: string;
}

export const listTeamspaces = (workspaceId: string) =>
	get<Teamspace[]>(`/api/v1/workspaces/${workspaceId}/teamspaces`);

export const createTeamspace = (workspaceId: string, name: string, icon = 'T') =>
	post<Teamspace>(`/api/v1/workspaces/${workspaceId}/teamspaces`, { name, icon });

export const teamspaceDocuments = (teamspaceId: string) =>
	get<Document[]>(`/api/v1/teamspaces/${teamspaceId}/documents`);

export const teamspaceMembers = (teamspaceId: string) =>
	get<TeamspaceMember[]>(`/api/v1/teamspaces/${teamspaceId}/members`);

export const addTeamspaceMember = (teamspaceId: string, userId: string, role: ShareRole) =>
	post<TeamspaceMember>(`/api/v1/teamspaces/${teamspaceId}/members`, {
		user_id: userId,
		role
	});

// ---- favourites ------------------------------------------------------------

export const listFavorites = () => get<Document[]>('/api/v1/favorites');
export const addFavorite = (documentId: string) =>
	post<void>('/api/v1/favorites', { document_id: documentId });
export const removeFavorite = (documentId: string) =>
	del<void>(`/api/v1/favorites/${documentId}`);
