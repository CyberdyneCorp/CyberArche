/** Database block ViewModel (database-block spec).
 *
 * Schema + rows live in a document-level Y.Map keyed `db:<blockId>` — the schema
 * under the reserved `__schema` key (whole-value LWW), and one entry per row id
 * (so concurrent edits to different rows merge). A debounced mirror writes
 * `{ properties, rows }` into the block's `data.db` for snapshots/agent/export,
 * matching the whiteboard block's pattern. */
import * as Y from 'yjs';

export type PropertyType = 'text' | 'number' | 'select' | 'checkbox' | 'date';

export interface SelectOption {
	id: string;
	name: string;
	color: string;
}

export interface Property {
	id: string;
	name: string;
	type: PropertyType;
	options?: SelectOption[];
}

export type CellValue = string | number | boolean | null;

export interface Row {
	id: string;
	order: number;
	values: Record<string, CellValue>;
}

export const OPTION_COLORS = [
	'#e11d48', '#f59e0b', '#10b981', '#3b82f6', '#8b5cf6', '#0ea5e9', '#ec4899', '#64748b'
];

const LOCAL = 'local';
const MIRROR_MS = 400;
const SCHEMA_KEY = '__schema';

function newId(): string {
	return crypto.randomUUID().replaceAll('-', '').slice(0, 12);
}

function defaultSchema(): Property[] {
	return [
		{ id: newId(), name: 'Name', type: 'text' },
		{
			id: newId(),
			name: 'Status',
			type: 'select',
			options: [
				{ id: newId(), name: 'To do', color: OPTION_COLORS[7] },
				{ id: newId(), name: 'Doing', color: OPTION_COLORS[3] },
				{ id: newId(), name: 'Done', color: OPTION_COLORS[2] }
			]
		}
	];
}

export interface DbSnapshot {
	properties: Property[];
	rows: Omit<Row, 'order'>[];
}

export function createDatabase(
	doc: Y.Doc,
	blockId: string,
	options: { initial?: DbSnapshot; onMirror?: (snapshot: DbSnapshot) => void } = {}
) {
	const ymap = doc.getMap<unknown>(`db:${blockId}`);
	let properties = $state<Property[]>([]);
	let rows = $state<Row[]>([]);
	let mirrorTimer: ReturnType<typeof setTimeout> | null = null;

	function mirror(): void {
		properties = ((ymap.get(SCHEMA_KEY) as Property[]) ?? []).map((p) => ({ ...p }));
		rows = [...ymap.entries()]
			.filter(([key]) => key !== SCHEMA_KEY)
			.map(([, row]) => row as Row)
			.sort((a, b) => a.order - b.order);
	}
	ymap.observe(mirror);
	mirror();

	// First open: hydrate from the mirrored snapshot, or seed a starter schema.
	if (ymap.size === 0) {
		doc.transact(() => {
			if (options.initial && options.initial.properties.length) {
				ymap.set(SCHEMA_KEY, options.initial.properties);
				options.initial.rows.forEach((r, i) =>
					ymap.set(r.id, { ...r, order: i } as Row)
				);
			} else {
				ymap.set(SCHEMA_KEY, defaultSchema());
			}
		}, LOCAL);
	}

	function scheduleMirror(): void {
		if (!options.onMirror) return;
		if (mirrorTimer) clearTimeout(mirrorTimer);
		mirrorTimer = setTimeout(() => {
			options.onMirror!({
				properties: (ymap.get(SCHEMA_KEY) as Property[]) ?? [],
				rows: [...ymap.entries()]
					.filter(([k]) => k !== SCHEMA_KEY)
					.map(([, r]) => {
						const { order: _order, ...rest } = r as Row;
						return rest;
					})
			});
		}, MIRROR_MS);
	}

	function schema(): Property[] {
		return (ymap.get(SCHEMA_KEY) as Property[]) ?? [];
	}
	function setSchema(next: Property[]): void {
		doc.transact(() => ymap.set(SCHEMA_KEY, next), LOCAL);
		scheduleMirror();
	}
	function putRow(row: Row): void {
		doc.transact(() => ymap.set(row.id, row), LOCAL);
		scheduleMirror();
	}

	const vm = {
		get properties() {
			return properties;
		},
		get rows() {
			return rows;
		},

		addProperty(type: PropertyType = 'text'): Property {
			const property: Property = {
				id: newId(),
				name: 'New',
				type,
				...(type === 'select' ? { options: [] } : {})
			};
			setSchema([...schema(), property]);
			return property;
		},
		removeProperty(id: string): void {
			setSchema(schema().filter((p) => p.id !== id));
		},
		renameProperty(id: string, name: string): void {
			setSchema(schema().map((p) => (p.id === id ? { ...p, name } : p)));
		},
		setPropertyType(id: string, type: PropertyType): void {
			setSchema(
				schema().map((p) =>
					p.id === id
						? { ...p, type, options: type === 'select' ? (p.options ?? []) : undefined }
						: p
				)
			);
		},
		addOption(propertyId: string, name: string): SelectOption {
			const option: SelectOption = {
				id: newId(),
				name,
				color: OPTION_COLORS[(schema().find((p) => p.id === propertyId)?.options?.length ?? 0) % OPTION_COLORS.length]
			};
			setSchema(
				schema().map((p) =>
					p.id === propertyId ? { ...p, options: [...(p.options ?? []), option] } : p
				)
			);
			return option;
		},

		addRow(values: Record<string, CellValue> = {}): Row {
			const order = rows.length ? Math.max(...rows.map((r) => r.order)) + 1 : 0;
			const row: Row = { id: newId(), order, values };
			putRow(row);
			return row;
		},
		removeRow(id: string): void {
			doc.transact(() => ymap.delete(id), LOCAL);
			scheduleMirror();
		},
		setCell(rowId: string, propertyId: string, value: CellValue): void {
			const row = ymap.get(rowId) as Row | undefined;
			if (!row) return;
			putRow({ ...row, values: { ...row.values, [propertyId]: value } });
		},
		/** Board: rows grouped by a select property's option (plus the "no value"
		 * bucket keyed ''). */
		groupBy(propertyId: string): Map<string, Row[]> {
			const groups = new Map<string, Row[]>();
			for (const row of rows) {
				const key = (row.values[propertyId] as string) || '';
				(groups.get(key) ?? groups.set(key, []).get(key)!).push(row);
			}
			return groups;
		},

		destroy(): void {
			if (mirrorTimer) clearTimeout(mirrorTimer);
			ymap.unobserve(mirror);
		}
	};
	return vm;
}

export type DatabaseVM = ReturnType<typeof createDatabase>;

/** Rows sorted by a property (display-only; does not mutate stored order). */
export function sortRows(rows: Row[], propertyId: string, dir: 'asc' | 'desc'): Row[] {
	const sign = dir === 'asc' ? 1 : -1;
	return [...rows].sort((a, b) => {
		const av = a.values[propertyId];
		const bv = b.values[propertyId];
		if (av == null && bv == null) return 0;
		if (av == null) return 1;
		if (bv == null) return -1;
		if (typeof av === 'number' && typeof bv === 'number') return (av - bv) * sign;
		return String(av).localeCompare(String(bv)) * sign;
	});
}
