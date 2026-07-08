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
});
