/** Whiteboard ViewModel (whiteboard-canvas spec).
 *
 * Elements live in a document-level Y.Map keyed `wb:<blockId>` — one entry
 * per element — so concurrent edits to DIFFERENT shapes merge perfectly
 * (spec 6.4); simultaneous edits to the same shape are last-write-wins.
 * A debounced mirror writes the scene into the block's `data.elements`,
 * which is what backend snapshots, the agent's context, and first-open
 * hydration read (agent-generated mind maps arrive this way).
 */

import * as Y from 'yjs';

export interface WhiteboardElement {
	id: string;
	kind: 'rect' | 'ellipse' | 'diamond' | 'text' | 'pen' | 'arrow';
	x: number;
	y: number;
	w: number;
	h: number;
	label: string;
	points?: number[][];
	from?: string; // bound connector endpoints (element ids)
	to?: string;
}

const LOCAL_ORIGIN = 'local';
const MIRROR_DEBOUNCE_MS = 400;

export function elementCenter(element: WhiteboardElement): { x: number; y: number } {
	return { x: element.x + element.w / 2, y: element.y + element.h / 2 };
}

/** Arrow endpoints follow their bound shapes (spec 6.2). */
export function arrowEndpoints(
	arrow: WhiteboardElement,
	byId: (id: string) => WhiteboardElement | undefined
): { x1: number; y1: number; x2: number; y2: number } {
	const from = arrow.from ? byId(arrow.from) : undefined;
	const to = arrow.to ? byId(arrow.to) : undefined;
	const start = from ? elementCenter(from) : { x: arrow.x, y: arrow.y };
	const end = to ? elementCenter(to) : { x: arrow.x + arrow.w, y: arrow.y + arrow.h };
	return { x1: start.x, y1: start.y, x2: end.x, y2: end.y };
}

export function createWhiteboard(
	doc: Y.Doc,
	blockId: string,
	options: {
		initialElements?: Record<string, WhiteboardElement>;
		onMirror?: (elements: Record<string, WhiteboardElement>) => void;
	} = {}
) {
	const ymap = doc.getMap<WhiteboardElement>(`wb:${blockId}`);
	let elements = $state<WhiteboardElement[]>([]);
	let selectedId = $state<string | null>(null);
	let mirrorTimer: ReturnType<typeof setTimeout> | null = null;

	function mirror(): void {
		elements = [...ymap.values()];
	}
	ymap.observe(mirror);
	mirror();

	// First open of a persisted/agent-generated scene: hydrate the Y.Map.
	if (ymap.size === 0 && options.initialElements) {
		doc.transact(() => {
			for (const [id, element] of Object.entries(options.initialElements!)) {
				ymap.set(id, element);
			}
		}, LOCAL_ORIGIN);
	}

	function scheduleMirrorToBlock(): void {
		if (!options.onMirror) return;
		if (mirrorTimer) clearTimeout(mirrorTimer);
		mirrorTimer = setTimeout(() => {
			options.onMirror!(Object.fromEntries(ymap.entries()));
		}, MIRROR_DEBOUNCE_MS);
	}

	function put(element: WhiteboardElement): void {
		doc.transact(() => ymap.set(element.id, element), LOCAL_ORIGIN);
		scheduleMirrorToBlock();
	}

	const vm = {
		get elements() {
			return elements;
		},
		get selectedId() {
			return selectedId;
		},
		byId(id: string): WhiteboardElement | undefined {
			return ymap.get(id);
		},
		select(id: string | null): void {
			selectedId = id;
		},

		addShape(
			kind: WhiteboardElement['kind'],
			x: number,
			y: number,
			w = 132,
			h = 46,
			label = ''
		): WhiteboardElement {
			const element: WhiteboardElement = {
				id: crypto.randomUUID().replaceAll('-', '').slice(0, 12),
				kind,
				x,
				y,
				w,
				h,
				label
			};
			put(element);
			selectedId = element.id;
			return element;
		},

		addPen(points: number[][]): WhiteboardElement {
			const xs = points.map((p) => p[0]);
			const ys = points.map((p) => p[1]);
			const element: WhiteboardElement = {
				id: crypto.randomUUID().replaceAll('-', '').slice(0, 12),
				kind: 'pen',
				x: Math.min(...xs),
				y: Math.min(...ys),
				w: Math.max(...xs) - Math.min(...xs),
				h: Math.max(...ys) - Math.min(...ys),
				label: '',
				points
			};
			put(element);
			return element;
		},

		connect(fromId: string, toId: string): WhiteboardElement {
			const element: WhiteboardElement = {
				id: crypto.randomUUID().replaceAll('-', '').slice(0, 12),
				kind: 'arrow',
				x: 0,
				y: 0,
				w: 0,
				h: 0,
				label: '',
				from: fromId,
				to: toId
			};
			put(element);
			return element;
		},

		/** Mind map (spec 6.3): a child node connected to its parent. */
		addChild(parentId: string): WhiteboardElement | null {
			const parent = ymap.get(parentId);
			if (!parent) return null;
			const siblings = [...ymap.values()].filter(
				(e) => e.kind === 'arrow' && e.from === parentId
			).length;
			const child = vm.addShape(
				'rect',
				parent.x + parent.w + 90,
				parent.y + siblings * 64 - 12,
				120,
				40,
				'New node'
			);
			vm.connect(parentId, child.id);
			selectedId = child.id;
			return child;
		},

		moveBy(id: string, dx: number, dy: number): void {
			const element = ymap.get(id);
			if (!element || element.kind === 'arrow') return;
			put({ ...element, x: element.x + dx, y: element.y + dy });
		},

		setLabel(id: string, label: string): void {
			const element = ymap.get(id);
			if (element) put({ ...element, label });
		},

		remove(id: string): void {
			doc.transact(() => {
				ymap.delete(id);
				// Cascade: connectors bound to the removed shape go too.
				for (const [key, element] of ymap.entries()) {
					if (element.kind === 'arrow' && (element.from === id || element.to === id)) {
						ymap.delete(key);
					}
				}
			}, LOCAL_ORIGIN);
			if (selectedId === id) selectedId = null;
			scheduleMirrorToBlock();
		},

		destroy(): void {
			if (mirrorTimer) clearTimeout(mirrorTimer);
			ymap.unobserve(mirror);
		}
	};
	return vm;
}

export type WhiteboardVM = ReturnType<typeof createWhiteboard>;
