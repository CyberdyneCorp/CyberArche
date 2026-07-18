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
	folder_id?: string | null;
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

/** One crumb of a document's breadcrumb path. */
export interface PathCrumb {
	kind: 'workspace' | 'teamspace' | 'folder' | 'document';
	id: string;
	label: string;
}

/** The document's breadcrumb path: workspace → teamspace? → folders →
 * ancestor documents → the document itself. */
export const getDocumentPath = (id: string) =>
	get<PathCrumb[]>(`/api/v1/documents/${id}/path`);

/** A document's current block tree (for reading content outside the editor,
 * e.g. exporting a whole teamspace/folder). */
export const documentBlocks = (id: string) =>
	get<{ blocks: import('$lib/editor/registry').BlockData[] }>(
		`/api/v1/documents/${id}/blocks`
	);

/** Title search within a workspace (empty query returns all accessible docs). */
export const searchDocuments = (workspaceId: string, q = '', limit = 50) =>
	get<Document[]>(
		`/api/v1/workspaces/${workspaceId}/search?${new URLSearchParams({ q, limit: String(limit) })}`
	);

/** Documents that reference this one via a [[title]] wikilink. */
export const backlinks = (documentId: string) =>
	get<Document[]>(`/api/v1/documents/${documentId}/backlinks`);

/** Documents in the workspace's trash (soft-deleted, restorable). */
export const listTrashed = (workspaceId: string) =>
	get<Document[]>(`/api/v1/workspaces/${workspaceId}/trash`);

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
