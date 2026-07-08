/** Editor ViewModel (block-editor spec 5.7): owns the Y.Doc binding,
 * block operations, undo/redo, focus, presence, and connection status.
 * Views render blocks through the registry and call commands here. */

import * as Y from 'yjs';

import { ArcheProvider, type PresencePeer, type ProviderStatus } from '$lib/crdt/provider';
import {
	allBlockDefinitions,
	markdownTransforms,
	newBlock,
	type BlockData,
	type BlockDefinition
} from '$lib/editor/registry';

const LOCAL_ORIGIN = 'local';
const PEER_COLORS = ['var(--rose)', 'var(--teal)', 'var(--blue)', 'var(--ok)'];

export function colorFor(userId: string): string {
	let hash = 0;
	for (const char of userId) hash = (hash * 31 + char.charCodeAt(0)) | 0;
	return PEER_COLORS[Math.abs(hash) % PEER_COLORS.length];
}

export function createEditor(documentId: string, token: string, userId: string) {
	const provider = new ArcheProvider(documentId, token);
	const yblocks = provider.doc.getArray<Y.Map<unknown>>('blocks');
	const undoManager = new Y.UndoManager(yblocks, {
		trackedOrigins: new Set([LOCAL_ORIGIN])
	});

	let blocks = $state<BlockData[]>([]);
	let status = $state<ProviderStatus>('connecting');
	let peers = $state<PresencePeer[]>([]);
	let focusedId = $state<string | null>(null);
	let canUndo = $state(false);
	let canRedo = $state(false);
	let readOnly = $state(false);
	let slashFor = $state<string | null>(null); // block id with an open slash menu
	let slashQuery = $state('');

	function mirror(): void {
		blocks = yblocks.toArray().map((item) => item.toJSON() as BlockData);
	}
	function refreshHistory(): void {
		canUndo = undoManager.undoStack.length > 0;
		canRedo = undoManager.redoStack.length > 0;
	}

	yblocks.observeDeep(mirror);
	mirror();
	undoManager.on('stack-item-added', refreshHistory);
	undoManager.on('stack-item-popped', refreshHistory);

	provider.onStatus = (next) => (status = next);
	provider.onPeers = (next) => (peers = next.filter((p) => p.user_id !== userId));
	provider.onDenied = () => (readOnly = true);
	provider.onSynced = () => {
		// Seed an empty document only once the server state is known.
		if (yblocks.length === 0) vm.insertAfter(null, 'paragraph');
	};

	function indexOf(id: string): number {
		return yblocks.toArray().findIndex((item) => item.get('id') === id);
	}

	function toYMap(block: BlockData): Y.Map<unknown> {
		const map = new Y.Map<unknown>();
		map.set('id', block.id);
		map.set('type', block.type);
		map.set('data', block.data);
		return map;
	}

	function transact(fn: () => void): void {
		provider.doc.transact(fn, LOCAL_ORIGIN);
	}

	const vm = {
		get blocks() {
			return blocks;
		},
		get status() {
			return status;
		},
		get peers() {
			return peers;
		},
		get focusedId() {
			return focusedId;
		},
		get canUndo() {
			return canUndo;
		},
		get canRedo() {
			return canRedo;
		},
		get readOnly() {
			return readOnly;
		},
		/** The shared Y.Doc — heavy blocks (whiteboard) attach their own
		 * fine-grained structures to it. */
		get doc() {
			return provider.doc;
		},
		userId,

		/** Insert a new block after `afterId` (or append); returns its id. */
		insertAfter(afterId: string | null, type: string): string {
			const block = newBlock(type);
			transact(() => {
				const index = afterId === null ? yblocks.length : indexOf(afterId) + 1;
				yblocks.insert(index === 0 ? yblocks.length : index, [toYMap(block)]);
			});
			focusedId = block.id;
			return block.id;
		},

		updateData(id: string, patch: Record<string, unknown>): void {
			const index = indexOf(id);
			if (index < 0) return;
			const map = yblocks.get(index);
			transact(() => {
				map.set('data', { ...(map.get('data') as object), ...patch });
			});
		},

		/** Turn a block into another type (markdown shortcuts, slash menu). */
		transform(id: string, type: string, data: Record<string, unknown>): void {
			const index = indexOf(id);
			if (index < 0) return;
			const map = yblocks.get(index);
			transact(() => {
				map.set('type', type);
				map.set('data', data);
			});
			focusedId = id;
		},

		remove(id: string): { previousId: string | null } {
			const index = indexOf(id);
			if (index < 0) return { previousId: null };
			const previous = index > 0 ? (yblocks.get(index - 1).get('id') as string) : null;
			// Close the capture window first: Yjs merges operations within
			// ~500ms into one undo step, so a quick type-then-delete would be
			// undone as a single action and the block could not be recovered.
			// A deletion is always its own undo step (block-editor spec).
			undoManager.stopCapturing();
			transact(() => yblocks.delete(index, 1));
			undoManager.stopCapturing();
			focusedId = previous;
			return { previousId: previous };
		},

		move(id: string, direction: -1 | 1): void {
			const index = indexOf(id);
			const target = index + direction;
			if (index < 0 || target < 0 || target >= yblocks.length) return;
			transact(() => {
				const snapshot = yblocks.get(index).toJSON() as BlockData;
				yblocks.delete(index, 1);
				yblocks.insert(target, [toYMap(snapshot)]);
			});
		},

		/** Split a paragraph-like block at a text offset (Enter mid-text). */
		splitText(id: string, before: string, after: string): string {
			vm.updateData(id, { text: before });
			const newId = vm.insertAfter(id, 'paragraph');
			vm.updateData(newId, { text: after });
			return newId;
		},

		focus(id: string | null): void {
			focusedId = id;
			if (id !== slashFor) vm.closeSlash();
			provider.broadcastPresence(id, userId, colorFor(userId));
		},

		// ---- slash menu + markdown shortcuts (block-editor spec 5.2) --------

		get slashFor() {
			return slashFor;
		},
		get slashQuery() {
			return slashQuery;
		},
		get slashMatches(): BlockDefinition[] {
			const query = slashQuery.toLowerCase();
			return allBlockDefinitions().filter(
				(d) => d.label.toLowerCase().includes(query) || d.type.includes(query)
			);
		},
		closeSlash(): void {
			slashFor = null;
			slashQuery = '';
		},
		applySlash(type: string): void {
			if (!slashFor) return;
			const id = slashFor;
			vm.closeSlash();
			const definition = newBlock(type);
			vm.transform(id, type, definition.data);
		},

		/** Route text input from paragraph-like blocks: opens the slash menu
		 * on "/", applies markdown-style prefixes, otherwise stores text. */
		handleTextInput(id: string, text: string): void {
			if (text.startsWith('/')) {
				slashFor = id;
				slashQuery = text.slice(1);
				vm.updateData(id, { text });
				return;
			}
			vm.closeSlash();
			for (const definition of markdownTransforms()) {
				const match = definition.markdownPrefix!.exec(text);
				if (match) {
					const rest = text.slice(match[0].length);
					vm.transform(id, definition.type, {
						...(definition.fromMarkdown?.(match) ?? definition.create()),
						text: rest
					});
					return;
				}
			}
			vm.updateData(id, { text });
		},

		undo(): void {
			undoManager.undo();
			refreshHistory();
		},
		redo(): void {
			undoManager.redo();
			refreshHistory();
		},

		/** Seed an empty document with one paragraph so typing can start. */
		ensureNotEmpty(): void {
			if (yblocks.length === 0) vm.insertAfter(null, 'paragraph');
		},

		destroy(): void {
			yblocks.unobserveDeep(mirror);
			provider.destroy();
		}
	};
	return vm;
}

export type EditorVM = ReturnType<typeof createEditor>;
