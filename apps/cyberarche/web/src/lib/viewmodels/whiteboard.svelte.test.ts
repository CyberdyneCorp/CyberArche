import { beforeAll, describe, expect, it, vi } from 'vitest';
import * as Y from 'yjs';

import {
	arrowEndpoints,
	createWhiteboard,
	type WhiteboardElement
} from './whiteboard.svelte';

beforeAll(() => {
	vi.stubGlobal('crypto', {
		randomUUID: () => `${Math.random().toString(16).slice(2)}-x-x-x-x`
	});
});

/** Two Y.Docs relaying updates to each other (a tiny in-memory network). */
function connectedPair(): [Y.Doc, Y.Doc] {
	const a = new Y.Doc();
	const b = new Y.Doc();
	a.on('update', (update: Uint8Array) => Y.applyUpdate(b, update));
	b.on('update', (update: Uint8Array) => Y.applyUpdate(a, update));
	return [a, b];
}

describe('whiteboard VM', () => {
	it('persists elements and restores a scene from block data', () => {
		const doc = new Y.Doc();
		const seed: Record<string, WhiteboardElement> = {
			root: { id: 'root', kind: 'rect', x: 10, y: 10, w: 100, h: 40, label: 'Root' }
		};
		const board = createWhiteboard(doc, 'blk', { initialElements: seed });

		expect(board.elements).toHaveLength(1);
		expect(board.byId('root')?.label).toBe('Root');

		// Reopening the same doc restores without duplicating.
		const reopened = createWhiteboard(doc, 'blk', { initialElements: seed });
		expect(reopened.elements).toHaveLength(1);
	});

	it('bound arrows follow their shapes when moved (6.2)', () => {
		const doc = new Y.Doc();
		const board = createWhiteboard(doc, 'blk');
		const a = board.addShape('rect', 0, 0, 100, 40);
		const b = board.addShape('rect', 300, 0, 100, 40);
		const arrow = board.connect(a.id, b.id);

		const before = arrowEndpoints(board.byId(arrow.id)!, (id) => board.byId(id));
		expect(before).toMatchObject({ x1: 50, y1: 20, x2: 350, y2: 20 });

		board.moveBy(b.id, 0, 200);
		const after = arrowEndpoints(board.byId(arrow.id)!, (id) => board.byId(id));
		expect(after.y2).toBe(220); // endpoint tracked the shape
		expect(after.y1).toBe(20);
	});

	it('concurrent edits to different shapes both survive (6.4)', () => {
		const [docA, docB] = connectedPair();
		const boardA = createWhiteboard(docA, 'blk');
		const one = boardA.addShape('rect', 0, 0);
		const two = boardA.addShape('ellipse', 200, 0);
		const boardB = createWhiteboard(docB, 'blk');
		expect(boardB.elements).toHaveLength(2);

		// A moves shape one while B moves shape two.
		boardA.moveBy(one.id, 0, 100);
		boardB.moveBy(two.id, 0, 300);

		for (const board of [boardA, boardB]) {
			expect(board.byId(one.id)?.y).toBe(100);
			expect(board.byId(two.id)?.y).toBe(300);
		}
	});

	it('mind map: add-child creates a connected node (6.3)', () => {
		const doc = new Y.Doc();
		const board = createWhiteboard(doc, 'blk');
		const root = board.addShape('rect', 50, 50, 120, 40, 'Root');

		const child = board.addChild(root.id)!;
		const grandchild = board.addChild(child.id)!;

		const arrows = board.elements.filter((e) => e.kind === 'arrow');
		expect(arrows).toHaveLength(2);
		expect(arrows.some((a) => a.from === root.id && a.to === child.id)).toBe(true);
		expect(arrows.some((a) => a.from === child.id && a.to === grandchild.id)).toBe(true);
		expect(child.x).toBeGreaterThan(root.x); // laid out as a branch
	});

	it('removing a shape cascades its connectors', () => {
		const doc = new Y.Doc();
		const board = createWhiteboard(doc, 'blk');
		const root = board.addShape('rect', 0, 0);
		const child = board.addChild(root.id)!;

		board.remove(child.id);

		expect(board.elements.filter((e) => e.kind === 'arrow')).toHaveLength(0);
		expect(board.byId(root.id)).toBeDefined();
	});

	it('mirrors the scene into block data for snapshots and the agent', async () => {
		vi.useFakeTimers();
		const doc = new Y.Doc();
		let mirrored: Record<string, WhiteboardElement> | null = null;
		const board = createWhiteboard(doc, 'blk', {
			onMirror: (elements) => (mirrored = elements)
		});

		board.addShape('rect', 5, 5, 80, 30, 'A');
		await vi.advanceTimersByTimeAsync(500);

		expect(mirrored).not.toBeNull();
		expect(Object.values(mirrored!)[0].label).toBe('A');
		vi.useRealTimers();
	});

	it('addImage stores the source and places an image element', () => {
		const board = createWhiteboard(new Y.Doc(), 'b1');
		const image = board.addImage('data:image/png;base64,AAAA', 20, 30);
		expect(image.kind).toBe('image');
		expect(image.src).toBe('data:image/png;base64,AAAA');
		expect(board.byId(image.id)?.kind).toBe('image');
	});

	it('setStyle updates one element and leaves others untouched', () => {
		const board = createWhiteboard(new Y.Doc(), 'b1');
		const a = board.addShape('rect', 0, 0);
		const b = board.addShape('rect', 0, 100);

		board.setStyle(a.id, { fill: '#f00', stroke: '#00f' });

		expect(board.byId(a.id)?.fill).toBe('#f00');
		expect(board.byId(a.id)?.stroke).toBe('#00f');
		expect(board.byId(b.id)?.fill).toBeUndefined(); // per-element
		expect(board.byId(a.id)?.label).toBe(''); // merged, other fields intact
	});

	it('an image and a style survive a scene round-trip through block data', () => {
		const board = createWhiteboard(new Y.Doc(), 'b1');
		const image = board.addImage('data:image/png;base64,ZZ', 5, 5);
		const shape = board.addShape('ellipse', 40, 40);
		board.setStyle(shape.id, { fill: '#0f0' });

		// The scene as block data would persist it (what the debounced mirror
		// writes): every element keyed by id.
		const scene = Object.fromEntries(board.elements.map((e) => [e.id, e]));
		const restored = createWhiteboard(new Y.Doc(), 'b2', { initialElements: scene });

		expect(restored.byId(image.id)?.src).toBe('data:image/png;base64,ZZ');
		expect(restored.byId(shape.id)?.fill).toBe('#0f0');
	});

	it('select tracks selection and remove clears it only for the removed id', () => {
		const board = createWhiteboard(new Y.Doc(), 'b1');
		const a = board.addShape('rect', 0, 0);
		const b = board.addShape('rect', 100, 0);
		expect(board.selectedId).toBe(b.id); // addShape selects the new element

		board.select(a.id);
		board.remove(b.id);
		expect(board.selectedId).toBe(a.id); // untouched by other removals

		board.remove(a.id);
		expect(board.selectedId).toBeNull();
	});

	it('setLabel renames an element; unknown ids are ignored', () => {
		const board = createWhiteboard(new Y.Doc(), 'b1');
		const a = board.addShape('rect', 0, 0, 132, 46, 'Old');

		board.setLabel(a.id, 'Named');
		expect(board.byId(a.id)?.label).toBe('Named');

		board.setLabel('missing', 'x');
		board.setStyle('missing', { fill: '#000' });
		expect(board.elements).toHaveLength(1);
	});

	it('moveBy ignores arrows and unknown ids', () => {
		const board = createWhiteboard(new Y.Doc(), 'b1');
		const a = board.addShape('rect', 0, 0);
		const b = board.addShape('rect', 200, 0);
		const arrow = board.connect(a.id, b.id);

		board.moveBy(arrow.id, 50, 50); // arrows follow shapes, never move directly
		expect(board.byId(arrow.id)).toMatchObject({ x: 0, y: 0 });

		board.moveBy('missing', 5, 5);
		expect(board.elements).toHaveLength(3);
	});

	it('addPen bounds the stroke to its points', () => {
		const board = createWhiteboard(new Y.Doc(), 'b1');
		const pen = board.addPen([
			[10, 40],
			[30, 20],
			[50, 60]
		]);

		expect(pen).toMatchObject({ kind: 'pen', x: 10, y: 20, w: 40, h: 40 });
		expect(board.byId(pen.id)?.points).toEqual([
			[10, 40],
			[30, 20],
			[50, 60]
		]);
	});

	it('addChild returns null for a missing parent and stacks siblings', () => {
		const board = createWhiteboard(new Y.Doc(), 'b1');
		expect(board.addChild('missing')).toBeNull();

		const root = board.addShape('rect', 0, 0, 100, 40);
		const first = board.addChild(root.id)!;
		const second = board.addChild(root.id)!;

		expect(second.y).toBe(first.y + 64); // laid out below the sibling
		expect(board.selectedId).toBe(second.id);
	});

	it('rapid edits collapse into one debounced mirror, and destroy cancels it', async () => {
		vi.useFakeTimers();
		const onMirror = vi.fn();
		const board = createWhiteboard(new Y.Doc(), 'b1', { onMirror });

		board.addShape('rect', 0, 0);
		board.addShape('rect', 10, 10);
		await vi.advanceTimersByTimeAsync(500);
		expect(onMirror).toHaveBeenCalledTimes(1); // debounced into one write
		expect(Object.keys(onMirror.mock.calls[0][0])).toHaveLength(2);

		board.addShape('rect', 20, 20);
		board.destroy();
		await vi.advanceTimersByTimeAsync(1000);
		expect(onMirror).toHaveBeenCalledTimes(1); // pending mirror cancelled
		vi.useRealTimers();
	});

	it('remove mirrors the pruned scene into block data', async () => {
		vi.useFakeTimers();
		const onMirror = vi.fn();
		const board = createWhiteboard(new Y.Doc(), 'b1', { onMirror });
		const a = board.addShape('rect', 0, 0);
		await vi.advanceTimersByTimeAsync(500);

		board.remove(a.id);
		await vi.advanceTimersByTimeAsync(500);

		expect(onMirror).toHaveBeenLastCalledWith({});
		vi.useRealTimers();
	});

	it('destroy detaches the element mirror', () => {
		const doc = new Y.Doc();
		const board = createWhiteboard(doc, 'b1');
		board.addShape('rect', 0, 0);
		board.destroy(); // no pending mirror timer to clear

		doc.getMap<WhiteboardElement>('wb:b1').set('x', {
			id: 'x',
			kind: 'rect',
			x: 0,
			y: 0,
			w: 1,
			h: 1,
			label: ''
		});
		expect(board.elements).toHaveLength(1); // no longer mirrored
	});
});
