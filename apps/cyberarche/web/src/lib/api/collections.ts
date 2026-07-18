/** Collections API client (Model layer): Notion-style databases whose rows are
 * documents. Only ViewModels import this — never Views directly. */

import { del, get, patch, post } from './http';

export type PropertyType =
	| 'text'
	| 'number'
	| 'select'
	| 'multi_select'
	| 'date'
	| 'checkbox'
	| 'url';

export type ViewKind = 'table' | 'board' | 'gallery' | 'calendar';

export interface PropertyDef {
	id: string;
	name: string;
	type: PropertyType;
	options: string[];
}

export interface Filter {
	property_id: string;
	op: string;
	value?: unknown;
}

export interface Sort {
	property_id: string;
	direction: 'asc' | 'desc';
}

export interface View {
	id: string;
	name: string;
	kind: ViewKind;
	filters: Filter[];
	sorts: Sort[];
	group_by: string | null;
	date_by: string | null;
}

export interface Collection {
	id: string;
	workspace_id: string;
	name: string;
	properties: PropertyDef[];
	views: View[];
	created_at: string;
}

export interface CollectionRow {
	id: string;
	workspace_id: string;
	title: string;
	collection_id: string | null;
	properties: Record<string, unknown>;
	created_at: string;
	updated_at: string;
}

export const listCollections = (workspaceId: string) =>
	get<Collection[]>(`/api/v1/workspaces/${workspaceId}/collections`);

export const createCollection = (workspaceId: string, name: string) =>
	post<Collection>(`/api/v1/workspaces/${workspaceId}/collections`, { name });

export const getCollection = (collectionId: string) =>
	get<Collection>(`/api/v1/collections/${collectionId}`);

export const renameCollection = (collectionId: string, name: string) =>
	patch<Collection>(`/api/v1/collections/${collectionId}`, { name });

export const deleteCollection = (collectionId: string) =>
	del<void>(`/api/v1/collections/${collectionId}`);

export const addProperty = (
	collectionId: string,
	name: string,
	type: PropertyType,
	options: string[] = []
) =>
	post<Collection>(`/api/v1/collections/${collectionId}/properties`, {
		name,
		type,
		options
	});

export const updateProperty = (
	collectionId: string,
	propertyId: string,
	patchBody: { name?: string; options?: string[] }
) => patch<Collection>(`/api/v1/collections/${collectionId}/properties/${propertyId}`, patchBody);

export const removeProperty = (collectionId: string, propertyId: string) =>
	del<Collection>(`/api/v1/collections/${collectionId}/properties/${propertyId}`);

export const createView = (collectionId: string, name: string, kind: ViewKind = 'table') =>
	post<View>(`/api/v1/collections/${collectionId}/views`, { name, kind });

export const updateView = (
	collectionId: string,
	viewId: string,
	patchBody: {
		name?: string;
		filters?: Filter[];
		sorts?: Sort[];
		group_by?: string | null;
		date_by?: string | null;
	}
) => patch<View>(`/api/v1/collections/${collectionId}/views/${viewId}`, patchBody);

export const deleteView = (collectionId: string, viewId: string) =>
	del<void>(`/api/v1/collections/${collectionId}/views/${viewId}`);

export const addRow = (collectionId: string, title = '') =>
	post<CollectionRow>(`/api/v1/collections/${collectionId}/rows`, { title });

export const queryView = (collectionId: string, viewId: string) =>
	get<CollectionRow[]>(`/api/v1/collections/${collectionId}/views/${viewId}/rows`);

export const setRowValues = (
	collectionId: string,
	documentId: string,
	values: Record<string, unknown>
) =>
	patch<CollectionRow>(`/api/v1/collections/${collectionId}/rows/${documentId}`, {
		values
	});

export const deleteRow = (collectionId: string, documentId: string) =>
	del<void>(`/api/v1/collections/${collectionId}/rows/${documentId}`);
