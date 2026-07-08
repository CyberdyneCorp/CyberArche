import { del, get, post } from './http';

export type ShareRole = 'owner' | 'editor' | 'commenter' | 'viewer';
export type SharePermission = 'view' | 'comment' | 'edit';

export interface ShareLink {
	id: string;
	document_id: string;
	permission: SharePermission;
	created_at: string;
	expires_at: string | null;
	revoked: boolean;
}

export interface Comment {
	id: string;
	block_id: string;
	author_id: string;
	body: string;
	created_at: string;
	resolved: boolean;
}

export const inviteToWorkspace = (workspaceId: string, userId: string, role: ShareRole) =>
	post(`/api/v1/workspaces/${workspaceId}/invites`, { user_id: userId, role });

export const grantOnDocument = (documentId: string, userId: string, role: ShareRole) =>
	post(`/api/v1/documents/${documentId}/grants`, { user_id: userId, role });

export const createShareLink = (documentId: string, permission: SharePermission) =>
	post<ShareLink>(`/api/v1/documents/${documentId}/share-links`, { permission });

export const listShareLinks = (documentId: string) =>
	get<ShareLink[]>(`/api/v1/documents/${documentId}/share-links`);

export const revokeShareLink = (documentId: string, linkId: string) =>
	del<ShareLink>(`/api/v1/documents/${documentId}/share-links/${linkId}`);

export const addComment = (documentId: string, blockId: string, body: string) =>
	post<Comment>(`/api/v1/documents/${documentId}/comments`, { block_id: blockId, body });

export const listComments = (documentId: string) =>
	get<Comment[]>(`/api/v1/documents/${documentId}/comments`);

export const resolveComment = (documentId: string, commentId: string) =>
	post<Comment>(`/api/v1/documents/${documentId}/comments/${commentId}/resolve`);
