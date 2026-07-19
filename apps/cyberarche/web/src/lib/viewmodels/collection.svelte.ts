/** Collection ViewModels (MVVM logic layer, DOM-free).
 *
 * `createCollectionList` backs the sidebar's per-workspace collection list.
 * `createCollection` backs the collection route: it loads a collection and the
 * rows of the active view, and mutates schema/rows optimistically. */

import {
	addProperty,
	addRow as apiAddRow,
	createCollection as apiCreateCollection,
	createView,
	deleteRow as apiDeleteRow,
	getCollection,
	listCollections,
	queryView,
	renameCollection,
	setRowValues,
	updateView,
	type Collection,
	type CollectionRow,
	type Filter,
	type PropertyDef,
	type PropertyType,
	type Sort,
	type View,
	type ViewKind
} from '$lib/api/collections';
import { retitleDocument } from '$lib/api/documents';

/** The synthetic property id that targets a row's document title (mirrors the
 * backend `TITLE_PROPERTY`). Filters/sorts may target it; it behaves like text. */
export const TITLE_PROPERTY = '__title__';

const OP_LABELS: Record<string, string> = {
	eq: 'is',
	neq: 'is not',
	contains: 'contains',
	gt: 'greater than',
	lt: 'less than',
	is_empty: 'is empty',
	not_empty: 'is not empty'
};

// Operators the backend `apply_view` honours for each property type.
const OPS_BY_TYPE: Record<PropertyType, string[]> = {
	text: ['eq', 'neq', 'contains', 'is_empty', 'not_empty'],
	url: ['eq', 'neq', 'contains', 'is_empty', 'not_empty'],
	number: ['eq', 'neq', 'gt', 'lt', 'is_empty', 'not_empty'],
	select: ['eq', 'neq', 'is_empty', 'not_empty'],
	multi_select: ['contains', 'is_empty', 'not_empty'],
	date: ['eq', 'gt', 'lt', 'is_empty', 'not_empty'],
	checkbox: ['eq', 'neq'],
	// A formula's computed value may be numeric, text, or boolean, so offer the
	// full operator set; apply_view compares it the same as any other column.
	formula: ['eq', 'neq', 'contains', 'gt', 'lt', 'is_empty', 'not_empty']
};

/** Pure: the operators appropriate to a property type, as pickable options.
 * The Title pseudo-property is filtered as text — pass `'text'`. */
export function operatorsForType(type: PropertyType): { value: string; label: string }[] {
	return (OPS_BY_TYPE[type] ?? OPS_BY_TYPE.text).map((op) => ({ value: op, label: OP_LABELS[op] }));
}

/** One Board column: rows sharing a single-select option value (or the trailing
 * `key: null` "Uncategorized" bucket for empty / unknown values). */
export interface RowGroup {
	key: string | null;
	label: string;
	rows: CollectionRow[];
}

/** Pure: partition already-filtered/sorted rows into Board columns.
 *
 * One group per option of `property`, in the property's option order, followed
 * by a trailing "Uncategorized" group (`key: null`) for rows whose value is
 * empty or not one of the options. When `property` is undefined a single "All"
 * group holds every row. Within-group order mirrors the incoming row order. */
export function groupRows(rows: CollectionRow[], property: PropertyDef | undefined): RowGroup[] {
	if (!property) return [{ key: null, label: 'All', rows: [...rows] }];

	const groups: RowGroup[] = property.options.map((option) => ({
		key: option,
		label: option,
		rows: []
	}));
	const byKey = new Map(groups.map((g) => [g.key, g]));
	const uncategorized: RowGroup = { key: null, label: 'Uncategorized', rows: [] };

	for (const row of rows) {
		const value = row.properties[property.id];
		const bucket = (typeof value === 'string' && byKey.get(value)) || uncategorized;
		bucket.rows.push(row);
	}
	return [...groups, uncategorized];
}

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

	/** Persist a single property value, then reflect the server row locally so
	 * table cells and board cards move to their new group. */
	async function writeCell(rowId: string, propertyId: string, value: unknown) {
		try {
			replaceRow(await setRowValues(collectionId, rowId, { [propertyId]: value }));
		} catch (e) {
			error = e instanceof Error ? e.message : 'failed to update cell';
			await reloadRows(); // fall back to server truth on failure
		}
	}

	/** The single-select property the current Board groups by, if any. */
	const groupByProperty = (): PropertyDef | undefined => {
		const id = currentView()?.group_by;
		if (!id) return undefined;
		const property = collection?.properties.find((p) => p.id === id);
		return property?.type === 'select' ? property : undefined;
	};

	const selectProperties = (): PropertyDef[] =>
		collection?.properties.filter((p) => p.type === 'select') ?? [];

	/** Date properties available to anchor a Calendar view on. */
	const dateProperties = (): PropertyDef[] =>
		collection?.properties.filter((p) => p.type === 'date') ?? [];

	/** The date property the current Calendar is anchored on, if any. */
	const dateByProperty = (): PropertyDef | undefined => {
		const id = currentView()?.date_by;
		if (!id) return undefined;
		const property = collection?.properties.find((p) => p.id === id);
		return property?.type === 'date' ? property : undefined;
	};

	function replaceView(updated: View) {
		if (!collection) return;
		collection = {
			...collection,
			views: collection.views.map((v) => (v.id === updated.id ? updated : v))
		};
	}

	const filters = (): Filter[] => currentView()?.filters ?? [];
	const sorts = (): Sort[] => currentView()?.sorts ?? [];

	/** Persist a filter/sort patch to the current view, then re-query its rows so
	 * the table reflects filters-then-sorts. */
	async function persistView(patch: { filters?: Filter[]; sorts?: Sort[] }) {
		const view = currentView();
		if (!view) return;
		try {
			replaceView(await updateView(collectionId, view.id, patch));
			await reloadRows();
		} catch (e) {
			error = e instanceof Error ? e.message : 'failed to update view';
		}
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

		/** Create a view of the given kind, append it, select it, and load rows. */
		async createViewOfKind(name: string, kind: ViewKind): Promise<View | null> {
			if (!collection) return null;
			try {
				const view = await createView(collectionId, name, kind);
				collection = { ...collection, views: [...collection.views, view] };
				currentViewId = view.id;
				await reloadRows();
				return view;
			} catch (e) {
				error = e instanceof Error ? e.message : 'failed to create view';
				return null;
			}
		},

		// ---- Board grouping ----
		get groupByProperty() {
			return groupByProperty();
		},
		get selectProperties() {
			return selectProperties();
		},

		/** Set the Board's group-by property (null clears it). Updates the view
		 * in-memory immediately so the columns re-partition without a round-trip. */
		async setBoardGroupBy(propertyId: string | null) {
			const view = currentView();
			if (!view) return;
			replaceView({ ...view, group_by: propertyId });
			try {
				await updateView(collectionId, view.id, { group_by: propertyId });
			} catch (e) {
				error = e instanceof Error ? e.message : 'failed to set group-by';
			}
		},

		/** Move a card between Board columns by setting its grouping property. */
		setRowGroup(rowId: string, propertyId: string, value: string | null) {
			return writeCell(rowId, propertyId, value);
		},

		// ---- Calendar date anchoring ----
		get dateProperties() {
			return dateProperties();
		},
		get dateByProperty() {
			return dateByProperty();
		},

		/** Set the Calendar's date property (null clears it). Updates the view
		 * in-memory immediately so rows re-place without a round-trip. */
		async setDateBy(propertyId: string | null) {
			const view = currentView();
			if (!view) return;
			replaceView({ ...view, date_by: propertyId });
			try {
				await updateView(collectionId, view.id, { date_by: propertyId });
			} catch (e) {
				error = e instanceof Error ? e.message : 'failed to set date property';
			}
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

		setCell(rowId: string, propertyId: string, value: unknown) {
			return writeCell(rowId, propertyId, value);
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

		async addProperty(
			name: string,
			type: PropertyType,
			options: string[] = [],
			formula = ''
		) {
			try {
				collection = await addProperty(collectionId, name, type, options, formula);
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
		},

		// ---- Current-view filters ----
		get filters() {
			return filters();
		},
		get activeFilterCount() {
			return filters().length;
		},

		addFilter(propertyId: string, op: string, value?: unknown) {
			return persistView({ filters: [...filters(), { property_id: propertyId, op, value }] });
		},

		updateFilter(index: number, patch: Partial<Filter>) {
			return persistView({
				filters: filters().map((f, i) => (i === index ? { ...f, ...patch } : f))
			});
		},

		removeFilter(index: number) {
			return persistView({ filters: filters().filter((_, i) => i !== index) });
		},

		// ---- Current-view sorts (applied in order) ----
		get sorts() {
			return sorts();
		},
		get activeSortCount() {
			return sorts().length;
		},

		addSort(propertyId: string, direction: 'asc' | 'desc') {
			return persistView({
				sorts: [...sorts(), { property_id: propertyId, direction }]
			});
		},

		updateSort(index: number, patch: Partial<Sort>) {
			return persistView({
				sorts: sorts().map((s, i) => (i === index ? { ...s, ...patch } : s))
			});
		},

		removeSort(index: number) {
			return persistView({ sorts: sorts().filter((_, i) => i !== index) });
		},

		moveSort(index: number, dir: 'up' | 'down') {
			const next = [...sorts()];
			const target = index + (dir === 'up' ? -1 : 1);
			if (target < 0 || target >= next.length) return Promise.resolve();
			[next[index], next[target]] = [next[target], next[index]];
			return persistView({ sorts: next });
		}
	};
}

export type CollectionVM = ReturnType<typeof createCollection>;
export type CollectionListVM = ReturnType<typeof createCollectionList>;
