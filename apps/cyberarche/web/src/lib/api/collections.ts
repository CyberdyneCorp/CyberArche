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
	| 'url'
	| 'formula'
	| 'relation'
	| 'rollup';

/** The aggregation functions a rollup property may use. */
export type RollupFunction =
	| 'count'
	| 'sum'
	| 'average'
	| 'min'
	| 'max'
	| 'earliest'
	| 'latest'
	| 'list';

export type ViewKind = 'table' | 'board' | 'gallery' | 'calendar';

export interface PropertyDef {
	id: string;
	name: string;
	type: PropertyType;
	options: string[];
	/** Expression for a formula property; empty for every other type. */
	formula?: string;
	/** Relation: the target collection whose rows this property links to. */
	relation_collection_id?: string;
	/** Rollup: which relation property on this collection to follow. */
	rollup_relation_property_id?: string;
	/** Rollup: which target-collection property to aggregate ('__title__' for title). */
	rollup_target_property_id?: string;
	/** Rollup: the aggregation function. */
	rollup_function?: string;
	/** Date: reminder lead time in minutes. -1 = none; 0 = at the date; >0 = before. */
	reminder_minutes?: number;
}

/** Config for a relation/rollup property, passed to add/update. */
export interface RelationRollupConfig {
	relation_collection_id?: string;
	rollup_relation_property_id?: string;
	rollup_target_property_id?: string;
	rollup_function?: string;
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

/** A linked row's id + title (relation picker + relation-cell rendering). */
export interface RelatedRow {
	id: string;
	title: string;
}

/** A view's rows plus the id/title of every row they link to via relations. */
export interface CollectionRowsResult {
	rows: CollectionRow[];
	related: RelatedRow[];
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
	options: string[] = [],
	formula = '',
	config: RelationRollupConfig = {},
	reminderMinutes = -1
) =>
	post<Collection>(`/api/v1/collections/${collectionId}/properties`, {
		name,
		type,
		options,
		formula,
		relation_collection_id: config.relation_collection_id ?? '',
		rollup_relation_property_id: config.rollup_relation_property_id ?? '',
		rollup_target_property_id: config.rollup_target_property_id ?? '',
		rollup_function: config.rollup_function ?? '',
		reminder_minutes: reminderMinutes
	});

export const updateProperty = (
	collectionId: string,
	propertyId: string,
	patchBody: {
		name?: string;
		options?: string[];
		formula?: string;
		reminder_minutes?: number;
	} & RelationRollupConfig
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
	get<CollectionRowsResult>(`/api/v1/collections/${collectionId}/views/${viewId}/rows`);

/** The target collection's rows (id + title) for the relation row picker. */
export const listCollectionRows = (collectionId: string) =>
	get<RelatedRow[]>(`/api/v1/collections/${collectionId}/rows`);

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

/** Delete several rows at once; returns how many were actually removed. */
export const bulkDeleteRows = (collectionId: string, ids: string[]) =>
	post<{ deleted: number }>(`/api/v1/collections/${collectionId}/rows/bulk-delete`, { ids });

/** Set one property's value across several rows; returns how many were changed. */
export const bulkSetRows = (
	collectionId: string,
	ids: string[],
	propertyId: string,
	value: unknown
) =>
	post<{ updated: number }>(`/api/v1/collections/${collectionId}/rows/bulk-set`, {
		ids,
		property_id: propertyId,
		value
	});
