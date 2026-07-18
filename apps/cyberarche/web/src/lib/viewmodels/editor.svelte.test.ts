import { beforeAll, describe, expect, it, vi } from 'vitest';

// The editor VM opens a WebSocket via ArcheProvider — stub it out; these
// tests exercise the Y.Doc binding and commands locally. Instances are
// recorded so provider-driven callbacks (status, presence, denial, sync)
// can be fired from tests.
class FakeSocket {
	static instances: FakeSocket[] = [];
	onopen: (() => void) | null = null;
	binaryType = '';
	readyState = 0;
	send() {}
	close() {}
	onmessage: ((event: MessageEvent) => void) | null = null;
	onclose: ((event: CloseEvent) => void) | null = null;
	onerror: (() => void) | null = null;
	constructor() {
		FakeSocket.instances.push(this);
	}
}

import * as Y from 'yjs';

import { registerBuiltinBlocks } from '$lib/editor/blocks';
import { allBlockDefinitions, newBlock, registerBlock } from '$lib/editor/registry';
import { colorFor, createEditor, spliceText } from './editor.svelte';
import { transformText } from '$lib/api/agent';

// The inline "Ask AI" transform calls the agent API; stub it so the VM test
// exercises only the local apply-over-selection path.
vi.mock('$lib/api/agent', () => ({ transformText: vi.fn() }));

beforeAll(() => {
	vi.stubGlobal('WebSocket', FakeSocket as unknown as typeof WebSocket);
	vi.stubGlobal('crypto', {
		randomUUID: () => `${Math.random().toString(16).slice(2)}-x-x-x-x`
	});
	registerBuiltinBlocks();
});

function editor() {
	return createEditor(
		'doc-1',
		{ getAccessToken: () => 'token', tryRefresh: async () => false },
		'alice'
	);
}

function lastSocket() {
	return FakeSocket.instances[FakeSocket.instances.length - 1];
}

/** A relay frame: 0x00 = CRDT update, 0x01 = awareness/presence JSON. */
function binaryFrame(kind: 0x00 | 0x01, payload: Uint8Array): MessageEvent {
	const frame = new Uint8Array(payload.length + 1);
	frame[0] = kind;
	frame.set(payload, 1);
	return new MessageEvent('message', { data: frame.buffer });
}

function syncFrame(): MessageEvent {
	return binaryFrame(0x00, Y.encodeStateAsUpdate(new Y.Doc()));
}

function presenceFrame(peer: { user_id: string; block_id: string | null; color: string }) {
	return binaryFrame(0x01, new TextEncoder().encode(JSON.stringify(peer)));
}

describe('block registry (12.1)', () => {
	it('exposes every backend block family used by the editor', () => {
		const types = allBlockDefinitions().map((d) => d.type);
		for (const expected of [
			'paragraph',
			'heading',
			'bulleted_list',
			'numbered_list',
			'todo',
			'callout',
			'quote',
			'divider',
			'code',
			'latex',
			'mermaid',
			'table',
			'excalidraw'
		]) {
			expect(types).toContain(expected);
		}
	});

	it('hides the legacy whiteboard from the slash menu but keeps excalidraw', () => {
		const vm = editor();
		const slashTypes = vm.slashMatches.map((d) => d.type);
		expect(slashTypes).toContain('excalidraw');
		expect(slashTypes).not.toContain('whiteboard');
		// …while the legacy block stays registered so old documents still render.
		expect(allBlockDefinitions().map((d) => d.type)).toContain('whiteboard');
	});

	it('rejects duplicate registration and unknown types', () => {
		expect(() =>
			registerBlock({ ...allBlockDefinitions()[0] })
		).toThrow(/already registered/);
		expect(() => newBlock('hologram')).toThrow(/unknown block type/);
	});
});

describe('editor ViewModel', () => {
	it('insert, update, and mirror blocks from the CRDT', () => {
		const vm = editor();
		const id = vm.insertAfter(null, 'paragraph');
		vm.updateData(id, { text: 'hello' });

		expect(vm.blocks).toHaveLength(1);
		expect(vm.blocks[0].data.text).toBe('hello');
	});

	it('slash: "/" opens the menu, applySlash transforms the block', () => {
		const vm = editor();
		const id = vm.insertAfter(null, 'paragraph');

		vm.handleTextInput(id, '/co');
		expect(vm.slashFor).toBe(id);
		expect(vm.slashMatches.map((d) => d.type)).toContain('code');

		vm.applySlash('code');
		expect(vm.slashFor).toBeNull();
		expect(vm.blocks[0].type).toBe('code');
		expect(vm.blocks[0].data.language).toBe('python');
	});

	it('markdown shortcuts transform paragraphs', () => {
		const vm = editor();
		const id = vm.insertAfter(null, 'paragraph');

		vm.handleTextInput(id, '# ');
		expect(vm.blocks[0].type).toBe('heading');
		expect(vm.blocks[0].data.level).toBe(1);

		const second = vm.insertAfter(vm.blocks[0].id, 'paragraph');
		vm.handleTextInput(second, '- ');
		expect(vm.blocks[1].type).toBe('bulleted_list');

		const third = vm.insertAfter(vm.blocks[1].id, 'paragraph');
		vm.handleTextInput(third, '```');
		expect(vm.blocks[2].type).toBe('code');
	});

	it('splitText divides a block into two', () => {
		const vm = editor();
		const id = vm.insertAfter(null, 'paragraph');
		vm.updateData(id, { text: 'hello world' });

		vm.splitText(id, 'hello', ' world');

		expect(vm.blocks.map((b) => b.data.text)).toEqual(['hello', ' world']);
	});

	it('move reorders and remove focuses the previous block', () => {
		const vm = editor();
		const first = vm.insertAfter(null, 'paragraph');
		const second = vm.insertAfter(first, 'paragraph');
		vm.updateData(first, { text: 'one' });
		vm.updateData(second, { text: 'two' });

		vm.move(second, -1);
		expect(vm.blocks.map((b) => b.data.text)).toEqual(['two', 'one']);

		vm.remove(vm.blocks[1].id);
		expect(vm.blocks).toHaveLength(1);
		expect(vm.focusedId).toBe(vm.blocks[0].id);
	});

	it('setHeadingLevel changes an existing heading and promotes a paragraph', () => {
		const vm = editor();
		const id = vm.insertAfter(null, 'paragraph');
		vm.updateData(id, { text: 'Title' });

		vm.setHeadingLevel(id, 3);
		expect(vm.blocks[0].type).toBe('heading');
		expect(vm.blocks[0].data.level).toBe(3);
		expect(vm.blocks[0].data.text).toBe('Title'); // text preserved

		vm.setHeadingLevel(id, 1);
		expect(vm.blocks[0].data.level).toBe(1);
	});

	it('turnInto changes type while preserving text', () => {
		const vm = editor();
		const id = vm.insertAfter(null, 'paragraph');
		vm.updateData(id, { text: 'a task' });

		vm.turnInto(id, 'todo');
		expect(vm.blocks[0].type).toBe('todo');
		expect(vm.blocks[0].data.text).toBe('a task');
		expect(vm.blocks[0].data.checked).toBe(false); // default merged in
	});

	it('duplicate inserts a fresh-id copy just after the block', () => {
		const vm = editor();
		const first = vm.insertAfter(null, 'paragraph');
		vm.updateData(first, { text: 'copy me' });

		const copyId = vm.duplicate(first);
		expect(copyId).toBeTruthy();
		expect(vm.blocks).toHaveLength(2);
		expect(copyId).not.toBe(first);
		expect(vm.blocks[1].id).toBe(copyId);
		expect(vm.blocks[1].data.text).toBe('copy me');
		// Independent data object (mutating the copy must not touch the original).
		vm.updateData(copyId!, { text: 'changed' });
		expect(vm.blocks[0].data.text).toBe('copy me');
	});

	it('toggleMark wraps and unwraps a selection with a markdown marker', () => {
		const vm = editor();
		const id = vm.insertAfter(null, 'paragraph');
		vm.updateData(id, { text: 'the quick fox' });

		// Wrap "quick" (offsets 4..9) in bold.
		let sel = vm.toggleMark(id, '**', 4, 9);
		expect(vm.blocks[0].data.text).toBe('the **quick** fox');
		expect(sel).toEqual({ start: 6, end: 11 });

		// Re-applying over the returned selection unwraps (markers just outside).
		sel = vm.toggleMark(id, '**', sel.start, sel.end);
		expect(vm.blocks[0].data.text).toBe('the quick fox');
		expect(sel).toEqual({ start: 4, end: 9 });
	});

	it('toggleMark unwraps when markers sit inside the selection', () => {
		const vm = editor();
		const id = vm.insertAfter(null, 'paragraph');
		vm.updateData(id, { text: 'a `code` b' });
		// Select including the backticks (offsets 2..8 = "`code`").
		const sel = vm.toggleMark(id, '`', 2, 8);
		expect(vm.blocks[0].data.text).toBe('a code b');
		expect(sel).toEqual({ start: 2, end: 6 });
	});

	it('undo/redo round-trips local edits', () => {
		const vm = editor();
		vm.insertAfter(null, 'paragraph');
		expect(vm.blocks).toHaveLength(1);

		vm.undo();
		expect(vm.blocks).toHaveLength(0);
		expect(vm.canRedo).toBe(true);

		vm.redo();
		expect(vm.blocks).toHaveLength(1);
	});

	it('undo/redo bump historyRevision so focused fields re-sync', () => {
		// EditableText ignores value changes while focused (caret safety), so a
		// focused undo would be invisible unless historyRevision changes. Guard it.
		const vm = editor();
		const id = vm.insertAfter(null, 'paragraph');
		vm.handleTextInput(id, 'hello');
		expect(vm.blocks[0].data.text).toBe('hello');

		const before = vm.historyRevision;
		vm.undo();
		expect(vm.historyRevision).toBe(before + 1);

		vm.redo();
		expect(vm.historyRevision).toBe(before + 2);
	});

	it('heading shortcut honours the hash count (# -> h1, ### -> h3)', () => {
		// Regression: `create()` hard-coded level 2 and the captured `#{1,3}`
		// group was discarded, so `# ` and `### ` both produced an h2. The old
		// test only asserted `type === 'heading'`, so the spec's "level-1
		// heading" scenario passed while the behaviour was wrong.
		for (const [prefix, level] of [
			['# ', 1],
			['## ', 2],
			['### ', 3]
		] as const) {
			const vm = editor();
			const id = vm.insertAfter(null, 'paragraph');
			vm.handleTextInput(id, prefix);
			expect(vm.blocks[0].type).toBe('heading');
			expect(vm.blocks[0].data.level).toBe(level);
		}
	});

	it('slash-menu headings still use the default level', () => {
		// fromMarkdown must not leak into the non-markdown path.
		const vm = editor();
		const id = vm.insertAfter(null, 'paragraph');
		vm.handleTextInput(id, '/head');
		vm.applySlash('heading');
		expect(vm.blocks[0].data.level).toBe(2);
	});

	it('table data operations keep rows and columns consistent', () => {
		const vm = editor();
		const id = vm.insertAfter(null, 'table');
		const table = () => vm.blocks[0].data as { header: string[]; rows: string[][] };

		expect(table().header).toHaveLength(2);
		vm.updateData(id, {
			header: [...table().header, 'Column 3'],
			rows: table().rows.map((row) => [...row, ''])
		});
		expect(table().header).toHaveLength(3);
		expect(table().rows[0]).toHaveLength(3);
	});

	it('deleting a block is its own undo step, even right after typing', () => {
		// Regression: Yjs merges ops within ~500ms into one undo capture, so a
		// quick type-then-delete collapsed into a single step and Ctrl+Z wiped
		// both blocks instead of restoring the deleted one.
		const vm = editor();
		const first = vm.insertAfter(null, 'paragraph');
		const second = vm.insertAfter(first, 'paragraph');
		vm.updateData(second, { text: 'delete me' });
		expect(vm.blocks).toHaveLength(2);

		vm.remove(second);
		expect(vm.blocks).toHaveLength(1);

		vm.undo();
		expect(vm.blocks).toHaveLength(2);
		expect(vm.blocks[1].data.text).toBe('delete me'); // recovered, not wiped
	});

	it('mergeWithPrevious joins text into the previous block, one undo step', () => {
		const vm = editor();
		const first = vm.insertAfter(null, 'paragraph');
		vm.updateData(first, { text: 'hello ' });
		const second = vm.insertAfter(first, 'paragraph');
		vm.updateData(second, { text: 'world' });
		expect(vm.blocks).toHaveLength(2);

		const result = vm.mergeWithPrevious(second);
		expect(result).toEqual({ previousId: first, caret: 'hello '.length });
		expect(vm.blocks).toHaveLength(1);
		expect(vm.blocks[0].data.text).toBe('hello world');

		// One undo step restores both blocks and their original text.
		vm.undo();
		expect(vm.blocks.map((b) => b.data.text)).toEqual(['hello ', 'world']);
	});

	it('mergeWithPrevious is a no-op at the first block', () => {
		const vm = editor();
		const first = vm.insertAfter(null, 'paragraph');
		vm.updateData(first, { text: 'alone' });
		expect(vm.mergeWithPrevious(first)).toBeNull();
		expect(vm.blocks).toHaveLength(1);
	});

	it('insertBlocks appends typed blocks to the local doc as one undo step', () => {
		const vm = editor();
		vm.insertAfter(null, 'paragraph'); // seed one block

		vm.insertBlocks([
			{ id: 'x1', type: 'paragraph', data: { text: 'answer' } },
			{ id: 'x2', type: 'latex', data: { source: 'E=mc^2' } },
			{ id: 'x3', type: 'mermaid', data: { source: 'graph TD; A-->B' } }
		]);

		expect(vm.blocks.map((b) => b.type)).toEqual([
			'paragraph',
			'paragraph',
			'latex',
			'mermaid'
		]);
		expect(vm.blocks[2].data.source).toBe('E=mc^2');

		// One undo step removes all three inserted blocks.
		vm.undo();
		expect(vm.blocks).toHaveLength(1);
	});
});

describe('editor ViewModel — provider wiring', () => {
	it('colorFor deterministically assigns a palette colour', () => {
		expect(colorFor('alice')).toBe(colorFor('alice'));
		expect(colorFor('alice')).toMatch(/^var\(--/);
	});

	it('reflects connection status and seeds an empty doc on first sync', () => {
		const vm = editor();
		const sock = lastSocket();
		expect(vm.status).toBe('connecting');

		sock.onopen!();
		expect(vm.status).toBe('connected');
		expect(vm.blocks).toHaveLength(0);

		sock.onmessage!(syncFrame());
		expect(vm.blocks).toHaveLength(1); // seeded so typing can start
		expect(vm.blocks[0].type).toBe('paragraph');
	});

	it('does not seed a document that already has content on sync', () => {
		const vm = editor();
		vm.insertAfter(null, 'paragraph');

		lastSocket().onmessage!(syncFrame());
		expect(vm.blocks).toHaveLength(1);
	});

	it('exposes remote peers, excluding the local user', () => {
		const vm = editor(); // userId 'alice'
		const sock = lastSocket();

		sock.onmessage!(presenceFrame({ user_id: 'bob', block_id: null, color: 'red' }));
		expect(vm.peers.map((p) => p.user_id)).toEqual(['bob']);

		sock.onmessage!(presenceFrame({ user_id: 'alice', block_id: null, color: 'blue' }));
		expect(vm.peers.map((p) => p.user_id)).toEqual(['bob']); // own echo filtered
	});

	it('a NotAuthorized control message flips the editor read-only', () => {
		const vm = editor();
		expect(vm.readOnly).toBe(false);

		lastSocket().onmessage!(
			new MessageEvent('message', {
				data: JSON.stringify({ type: 'error', error: 'NotAuthorized' })
			})
		);
		expect(vm.readOnly).toBe(true);
	});

	it('exposes the shared Y.Doc and the local user id', () => {
		const vm = editor();
		expect(vm.userId).toBe('alice');
		expect(vm.doc).toBeInstanceOf(Y.Doc);
	});
});

describe('editor ViewModel — edge cases', () => {
	it('insertAfter with an unknown afterId appends at the end', () => {
		const vm = editor();
		const first = vm.insertAfter(null, 'paragraph');
		const id = vm.insertAfter('missing', 'paragraph');

		expect(vm.blocks.map((b) => b.id)).toEqual([first, id]);
		expect(vm.focusedId).toBe(id);
	});

	it('insertBlocks with an empty list is a no-op', () => {
		const vm = editor();
		vm.insertBlocks([]);
		expect(vm.blocks).toHaveLength(0);
		expect(vm.canUndo).toBe(false);
	});

	it('mutating commands ignore unknown block ids', () => {
		const vm = editor();
		const id = vm.insertAfter(null, 'paragraph');
		vm.updateData(id, { text: 'keep' });

		vm.updateData('missing', { text: 'x' });
		vm.transform('missing', 'code', {});
		vm.setHeadingLevel('missing', 2);
		vm.turnInto('missing', 'todo');
		vm.move('missing', 1);
		expect(vm.duplicate('missing')).toBeNull();
		expect(vm.remove('missing')).toEqual({ previousId: null });
		expect(vm.mergeWithPrevious('missing')).toBeNull();
		expect(vm.toggleMark('missing', '**', 0, 1)).toEqual({ start: 2, end: 3 });

		expect(vm.blocks).toHaveLength(1);
		expect(vm.blocks[0].type).toBe('paragraph');
		expect(vm.blocks[0].data.text).toBe('keep');
	});

	it('move is a no-op at the document edges', () => {
		const vm = editor();
		const first = vm.insertAfter(null, 'paragraph');
		const second = vm.insertAfter(first, 'paragraph');

		vm.move(first, -1);
		vm.move(second, 1);
		expect(vm.blocks.map((b) => b.id)).toEqual([first, second]);
	});

	it('removing the first block returns no previous id', () => {
		const vm = editor();
		const only = vm.insertAfter(null, 'paragraph');

		expect(vm.remove(only)).toEqual({ previousId: null });
		expect(vm.focusedId).toBeNull();
		expect(vm.blocks).toHaveLength(0);
	});

	it('toggleMark leaves a collapsed selection untouched', () => {
		const vm = editor();
		const id = vm.insertAfter(null, 'paragraph');
		vm.updateData(id, { text: 'abc' });

		expect(vm.toggleMark(id, '**', 2, 2)).toEqual({ start: 2, end: 2 });
		expect(vm.blocks[0].data.text).toBe('abc');
	});

	it('setHeadingLevel defaults missing text to empty when promoting', () => {
		const vm = editor();
		const id = vm.insertAfter(null, 'divider'); // no data.text

		vm.setHeadingLevel(id, 2);
		expect(vm.blocks[0].type).toBe('heading');
		expect(vm.blocks[0].data.text).toBe('');
	});

	it('focus closes menus opened on other blocks but keeps its own', () => {
		const vm = editor();
		const first = vm.insertAfter(null, 'paragraph');
		const second = vm.insertAfter(first, 'paragraph');

		vm.handleTextInput(first, '/co');
		vm.focus(first); // same block: the slash menu stays open
		expect(vm.slashFor).toBe(first);

		vm.focus(second); // another block: menu closes
		expect(vm.slashFor).toBeNull();
		expect(vm.focusedId).toBe(second);
	});

	it('applySlash without an open menu is a no-op', () => {
		const vm = editor();
		vm.insertAfter(null, 'paragraph');
		vm.applySlash('code');
		expect(vm.blocks[0].type).toBe('paragraph');
	});

	it('slashMatches filters out non-matching queries', () => {
		const vm = editor();
		const id = vm.insertAfter(null, 'paragraph');
		vm.handleTextInput(id, '/nosuchblock');

		expect(vm.slashQuery).toBe('nosuchblock');
		expect(vm.slashMatches).toHaveLength(0);
	});

	it('an unclosed [[ opens the link menu and applyLink completes it', () => {
		const vm = editor();
		const id = vm.insertAfter(null, 'paragraph');

		vm.handleTextInput(id, 'see [[cal');
		expect(vm.linkFor).toBe(id);
		expect(vm.linkQuery).toBe('cal');
		expect(vm.blocks[0].data.text).toBe('see [[cal');
		expect(Array.isArray(vm.linkMatches)).toBe(true);

		const before = vm.historyRevision;
		vm.applyLink('Calculus');
		expect(vm.blocks[0].data.text).toBe('see [[Calculus]]');
		expect(vm.linkFor).toBeNull();
		expect(vm.linkQuery).toBe('');
		expect(vm.historyRevision).toBe(before + 1); // focused field re-syncs
		expect(vm.focusedId).toBe(id);
	});

	it('opening [[ closes the slash menu, and closing ]] clears the link menu', () => {
		const vm = editor();
		const id = vm.insertAfter(null, 'paragraph');

		vm.handleTextInput(id, '/co');
		expect(vm.slashFor).toBe(id);

		vm.handleTextInput(id, '[[doc');
		expect(vm.slashFor).toBeNull();
		expect(vm.linkFor).toBe(id);

		vm.handleTextInput(id, '[[doc]] done');
		expect(vm.linkFor).toBeNull();
		expect(vm.blocks[0].data.text).toBe('[[doc]] done');
	});

	it('applyLink without an open menu is a no-op', () => {
		const vm = editor();
		const id = vm.insertAfter(null, 'paragraph');
		vm.updateData(id, { text: 'plain' });

		vm.applyLink('Calculus');
		expect(vm.blocks[0].data.text).toBe('plain');
	});

	it('ensureNotEmpty seeds a paragraph only when the doc is empty', () => {
		const vm = editor();
		vm.ensureNotEmpty();
		expect(vm.blocks).toHaveLength(1);

		vm.ensureNotEmpty();
		expect(vm.blocks).toHaveLength(1);
	});

	it('destroy detaches the CRDT mirror', () => {
		const vm = editor();
		vm.insertAfter(null, 'paragraph');
		vm.destroy();

		vm.insertAfter(null, 'paragraph'); // no longer mirrored into state
		expect(vm.blocks).toHaveLength(1);
	});
});

describe('inline "Ask AI" transform (inline-ai-selection)', () => {
	it('spliceText replaces only the selected range (before + result + after)', () => {
		expect(spliceText('hello world', 6, 11, 'planet')).toBe('hello planet');
		expect(spliceText('abc', 0, 3, 'XYZ')).toBe('XYZ');
		expect(spliceText('keep me', 0, 0, 'ins ')).toBe('ins keep me');
	});

	it('transformSelection applies the LLM result over the selection, undoably', async () => {
		vi.mocked(transformText).mockResolvedValue({ text: 'planet' });
		const vm = editor();
		const id = vm.insertAfter(null, 'paragraph');
		vm.updateData(id, { text: 'hello world' });

		const ok = await vm.transformSelection(
			{ blockId: id, start: 6, end: 11 },
			'rewrite'
		);

		expect(ok).toBe(true);
		// The selected text ("world") went to the API; the doc id and action too.
		expect(transformText).toHaveBeenCalledWith('doc-1', 'rewrite', 'world', undefined);
		expect(vm.blocks[0].data.text).toBe('hello planet');
		// The edit went through the tracked (undoable) local update path.
		expect(vm.canUndo).toBe(true);
	});

	it('transformSelection forwards the translation target language', async () => {
		vi.mocked(transformText).mockResolvedValue({ text: 'mundo' });
		const vm = editor();
		const id = vm.insertAfter(null, 'paragraph');
		vm.updateData(id, { text: 'world' });

		await vm.transformSelection({ blockId: id, start: 0, end: 5 }, 'translate', 'Español');

		expect(transformText).toHaveBeenCalledWith('doc-1', 'translate', 'world', 'Español');
		expect(vm.blocks[0].data.text).toBe('mundo');
	});

	it('transformSelection ignores a whitespace-only selection', async () => {
		vi.mocked(transformText).mockClear();
		const vm = editor();
		const id = vm.insertAfter(null, 'paragraph');
		vm.updateData(id, { text: 'a   b' });

		const ok = await vm.transformSelection({ blockId: id, start: 1, end: 4 }, 'rewrite');

		expect(ok).toBe(false);
		expect(transformText).not.toHaveBeenCalled();
		expect(vm.blocks[0].data.text).toBe('a   b');
	});
});
