import { beforeAll, describe, expect, it, vi } from 'vitest';

// The editor VM opens a WebSocket via ArcheProvider — stub it out; these
// tests exercise the Y.Doc binding and commands locally.
class FakeSocket {
	onopen: (() => void) | null = null;
	binaryType = '';
	readyState = 0;
	send() {}
	close() {}
	onmessage = null;
	onclose = null;
	onerror = null;
}

import { registerBuiltinBlocks } from '$lib/editor/blocks';
import { allBlockDefinitions, newBlock, registerBlock } from '$lib/editor/registry';
import { createEditor } from './editor.svelte';

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
