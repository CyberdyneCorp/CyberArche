/** Folders + private documents (add-folders-and-private). */
import { del, get, patch, post } from './http';
import type { Document } from './documents';

export interface Folder {
	id: string;
	workspace_id: string;
	name: string;
	teamspace_id: string | null;
	parent_folder_id: string | null;
	created_by: string;
	created_at: string;
}

export const listFolders = (workspaceId: string) =>
	get<Folder[]>(`/api/v1/workspaces/${workspaceId}/folders`);

export const createFolder = (
	workspaceId: string,
	name: string,
	teamspaceId?: string | null,
	parentFolderId?: string | null
) =>
	post<Folder>(`/api/v1/workspaces/${workspaceId}/folders`, {
		name,
		teamspace_id: teamspaceId ?? null,
		parent_folder_id: parentFolderId ?? null
	});

export const renameFolder = (folderId: string, name: string) =>
	patch<Folder>(`/api/v1/folders/${folderId}`, { name });

export const deleteFolder = (folderId: string) => del<void>(`/api/v1/folders/${folderId}`);

export const folderDocuments = (folderId: string) =>
	get<Document[]>(`/api/v1/folders/${folderId}/documents`);

export const placeInFolder = (documentId: string, folderId: string | null) =>
	post<Document>(`/api/v1/documents/${documentId}/folder`, { folder_id: folderId });

export const listPrivate = (workspaceId: string) =>
	get<Document[]>(`/api/v1/workspaces/${workspaceId}/private`);
