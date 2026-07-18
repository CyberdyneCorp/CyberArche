/** Collection ViewModels (MVVM logic layer, DOM-free).
 *
 * `createCollectionList` backs the sidebar's per-workspace collection list.
 * `createCollection` backs the collection route: it loads a collection and the
 * rows of the active view, and mutates schema/rows optimistically. */

import {
	addProperty,
	addRow as apiAddRow,
	createCollection as apiCreateCollection,
	deleteRow as apiDeleteRow,
	getCollection,
	listCollections,
	queryView,
	renameCollection,
	setRowValues,
	type Collection,
	type CollectionRow,
	type PropertyType,
	type View
} from '$lib/api/collections';
import { retitleDocument } from '$lib/api/documents';

export function createCollectionList(workspaceId: string) {
	let collections = $state<Collection[]>([]);
	let error = $state<string | null>(null);

	return {
		get collections() {
			return collections;
		},
		get error() {
			return error;
		},
		async load() {
			try {
				collections = await listCollections(workspaceId);
			} catch (e) {
				error = e instanceof Error ? e.message : 'failed to load collections';
			}
		},
		async create(name: string): Promise<Collection | null> {
			try {
				const created = await apiCreateCollection(workspaceId, name);
				collections = [...collections, created];
				return created;
			} catch (e) {
				error = e instanceof Error ? e.message : 'failed to create collection';
				return null;
			}
		}
	};
}

export function createCollection(collectionId: string) {
	let collection = $state<Collection | null>(null);
	let rows = $state<CollectionRow[]>([]);
	let currentViewId = $state<string | null>(null);
	let busy = $state(false);
	let error = $state<string | null>(null);

	const currentView = (): View | null =>
		collection?.views.find((v) => v.id === currentViewId) ?? null;

	async function reloadRows() {
		if (!currentViewId) return;
		rows = await queryView(collectionId, currentViewId);
	}

	function replaceRow(updated: CollectionRow) {
		rows = rows.map((r) => (r.id === updated.id ? updated : r));
	}

	return {
		get collection() {
			return collection;
		},
		get rows() {
			return rows;
		},
		get properties() {
			return collection?.properties ?? [];
		},
		get currentView() {
			return currentView();
		},
		get busy() {
			return busy;
		},
		get error() {
			return error;
		},

		async load() {
			busy = true;
			error = null;
			try {
				collection = await getCollection(collectionId);
				currentViewId = collection.views[0]?.id ?? null;
				await reloadRows();
			} catch (e) {
				error = e instanceof Error ? e.message : 'failed to load collection';
			} finally {
				busy = false;
			}
		},

		async selectView(viewId: string) {
			currentViewId = viewId;
			await reloadRows();
		},

		async addRow(title = ''): Promise<CollectionRow | null> {
			try {
				const row = await apiAddRow(collectionId, title);
				rows = [...rows, row];
				return row;
			} catch (e) {
				error = e instanceof Error ? e.message : 'failed to add row';
				return null;
			}
		},

		async setCell(rowId: string, propertyId: string, value: unknown) {
			try {
				const updated = await setRowValues(collectionId, rowId, { [propertyId]: value });
				replaceRow(updated);
			} catch (e) {
				error = e instanceof Error ? e.message : 'failed to update cell';
				await reloadRows(); // fall back to server truth on failure
			}
		},

		async deleteRow(rowId: string) {
			const previous = rows;
			rows = rows.filter((r) => r.id !== rowId); // optimistic
			try {
				await apiDeleteRow(collectionId, rowId);
			} catch (e) {
				error = e instanceof Error ? e.message : 'failed to delete row';
				rows = previous;
			}
		},

		async renameRow(rowId: string, title: string) {
			try {
				const updated = await retitleDocument(rowId, title);
				replaceRow({ ...(rows.find((r) => r.id === rowId) as CollectionRow), title: updated.title });
			} catch (e) {
				error = e instanceof Error ? e.message : 'failed to rename row';
			}
		},

		async addProperty(name: string, type: PropertyType, options: string[] = []) {
			try {
				collection = await addProperty(collectionId, name, type, options);
			} catch (e) {
				error = e instanceof Error ? e.message : 'failed to add property';
			}
		},

		async rename(name: string) {
			try {
				collection = await renameCollection(collectionId, name);
			} catch (e) {
				error = e instanceof Error ? e.message : 'failed to rename';
			}
		}
	};
}

export type CollectionVM = ReturnType<typeof createCollection>;
export type CollectionListVM = ReturnType<typeof createCollectionList>;
