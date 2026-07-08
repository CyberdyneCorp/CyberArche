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
	return createEditor('doc-1', 'token', 'alice');
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
			'table'
		]) {
			expect(types).toContain(expected);
		}
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
});
