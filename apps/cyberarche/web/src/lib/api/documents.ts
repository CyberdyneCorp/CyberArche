import { del, get, patch, post } from './http';

export interface Document {
	id: string;
	workspace_id: string;
	title: string;
	parent_id: string | null;
	position: number;
	created_by: string;
	created_at: string;
	updated_at: string;
	trashed: boolean;
	teamspace_id: string | null;
}

export const createDocument = (
	workspaceId: string,
	title = '',
	parentId?: string,
	teamspaceId?: string
) =>
	post<Document>('/api/v1/documents', {
		workspace_id: workspaceId,
		title,
		parent_id: parentId ?? null,
		teamspace_id: teamspaceId ?? null
	});

export const getDocument = (id: string) => get<Document>(`/api/v1/documents/${id}`);

export const listChildren = (workspaceId: string, parentId?: string) => {
	const params = new URLSearchParams({ workspace_id: workspaceId });
	if (parentId) params.set('parent_id', parentId);
	return get<Document[]>(`/api/v1/documents?${params}`);
};

export const retitleDocument = (id: string, title: string) =>
	patch<Document>(`/api/v1/documents/${id}/title`, { title });

export const trashDocument = (id: string) => del<Document>(`/api/v1/documents/${id}`);
export const restoreDocument = (id: string) =>
	post<Document>(`/api/v1/documents/${id}/restore`);
/** Permanently delete a trashed document and its subtree; returns the ids removed. */
export const purgeDocument = (id: string) => del<{ purged: string[] }>(`/api/v1/documents/${id}/trash`);
