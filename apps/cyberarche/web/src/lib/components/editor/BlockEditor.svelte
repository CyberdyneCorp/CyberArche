<script lang="ts">
	import { goto } from '$app/navigation';
	import CommentThread from '$lib/components/CommentThread.svelte';
	import ContextMenu, { type MenuItem } from '$lib/components/ContextMenu.svelte';
	import { blockDefinition } from '$lib/editor/registry';
	import { colorFor, type EditorVM } from '$lib/viewmodels/editor.svelte';
	import { documentTree } from '$lib/viewmodels/document-tree.svelte';
	import { linkIndex } from '$lib/viewmodels/link-index.svelte';
	import type { SharingVM } from '$lib/viewmodels/sharing.svelte';
	import LinkMenu from './LinkMenu.svelte';
	import SlashMenu from './SlashMenu.svelte';

	let { editor, sharing = null }: { editor: EditorVM; sharing?: SharingVM | null } =
		$props();

	let commentsFor = $state<string | null>(null);

	// ---- block / selection context menu (right-click) ----------------------
	// Text-family blocks share `data.text`, so they can turn into one another and
	// carry inline formatting; other types only get duplicate/delete.
	const TEXT_TYPES = new Set([
		'paragraph',
		'heading',
		'bulleted_list',
		'numbered_list',
		'todo',
		'quote',
		'callout'
	]);
	const TURN_INTO = [
		{ type: 'paragraph', label: 'Text', icon: '¶' },
		{ type: 'bulleted_list', label: 'Bulleted list', icon: '•' },
		{ type: 'numbered_list', label: 'Numbered list', icon: '1.' },
		{ type: 'todo', label: 'To-do', icon: '☐' },
		{ type: 'quote', label: 'Quote', icon: '❝' },
		{ type: 'callout', label: 'Callout', icon: '◆' }
	];

	type BlockMenu = {
		x: number;
		y: number;
		blockId: string;
		editable: HTMLElement | null;
		range: { start: number; end: number } | null;
	};
	let menu = $state<BlockMenu | null>(null);

	/** Absolute character offset of (node, off) within `el`'s text. */
	function offsetOf(el: HTMLElement, node: Node, off: number): number {
		const range = document.createRange();
		range.selectNodeContents(el);
		range.setEnd(node, off);
		return range.toString().length;
	}
	function selectionOffsets(el: HTMLElement): { start: number; end: number } | null {
		const sel = window.getSelection();
		if (!sel || sel.rangeCount === 0) return null;
		const range = sel.getRangeAt(0);
		const start = offsetOf(el, range.startContainer, range.startOffset);
		const end = offsetOf(el, range.endContainer, range.endOffset);
		return start <= end ? { start, end } : { start: end, end: start };
	}

	function onContextMenu(event: MouseEvent, block: { id: string; data: unknown }) {
		if (editor.readOnly) return;
		const editable = (event.target as HTMLElement).closest('.editable') as HTMLElement | null;
		let range: { start: number; end: number } | null = null;
		const sel = window.getSelection();
		if (
			editable &&
			sel &&
			!sel.isCollapsed &&
			sel.anchorNode &&
			editable.contains(sel.anchorNode)
		) {
			// Offsets are over the editable's text, which equals the stored markdown
			// source only while editing (raw source shown); guard so we never map a
			// rendered-HTML selection onto source offsets.
			const source = String((block.data as { text?: string })?.text ?? '');
			if ((editable.textContent ?? '') === source) range = selectionOffsets(editable);
		}
		event.preventDefault();
		menu = { x: event.clientX, y: event.clientY, blockId: block.id, editable, range };
	}

	/** Wrap/unwrap the stored selection in a markdown marker, then restore the
	 * highlight in the (raw-source) editable so the user can keep formatting. */
	function applyMark(marker: string) {
		if (!menu || !menu.range) return;
		const { blockId, editable, range } = menu;
		const res = editor.toggleMark(blockId, marker, range.start, range.end);
		menu = null;
		if (!editable) return;
		const fresh = String(
			(editor.blocks.find((b) => b.id === blockId)?.data as { text?: string })?.text ?? ''
		);
		editable.focus(); // onfocus flips to raw-source editing mode…
		editable.textContent = fresh; // …then we override with the updated source
		const node = editable.firstChild;
		if (node) {
			const restore = document.createRange();
			restore.setStart(node, Math.min(res.start, fresh.length));
			restore.setEnd(node, Math.min(res.end, fresh.length));
			const sel = window.getSelection();
			sel?.removeAllRanges();
			sel?.addRange(restore);
		}
	}

	function menuItems(): MenuItem[] {
		if (!menu) return [];
		const block = editor.blocks.find((b) => b.id === menu!.blockId);
		if (!block) return [];
		const items: MenuItem[] = [];
		if (menu.range) {
			items.push({ label: 'Format', heading: true });
			items.push({ label: 'Bold', icon: 'B', onSelect: () => applyMark('**') });
			items.push({ label: 'Italic', icon: 'I', onSelect: () => applyMark('*') });
			items.push({ label: 'Code', icon: '‹›', onSelect: () => applyMark('`') });
			items.push({ label: 'Strikethrough', icon: 'S', onSelect: () => applyMark('~~') });
			items.push({ separator: true });
		}
		if (block.type === 'heading') {
			items.push({ label: 'Heading level', heading: true });
			const level = Math.round(Number((block.data as { level?: number }).level) || 1);
			for (const lvl of [1, 2, 3, 4]) {
				items.push({
					label: `Heading ${lvl}`,
					active: level === lvl,
					onSelect: () => editor.setHeadingLevel(block.id, lvl)
				});
			}
			items.push({ separator: true });
		}
		if (TEXT_TYPES.has(block.type)) {
			items.push({ label: 'Turn into', heading: true });
			if (block.type !== 'heading') {
				items.push({
					label: 'Heading',
					icon: 'H',
					onSelect: () => editor.setHeadingLevel(block.id, 2)
				});
			}
			for (const target of TURN_INTO) {
				if (target.type === 'paragraph' && block.type === 'paragraph') continue;
				items.push({
					label: target.label,
					icon: target.icon,
					active: block.type === target.type,
					onSelect: () => editor.turnInto(block.id, target.type)
				});
			}
			items.push({ separator: true });
		}
		items.push({
			label: 'Duplicate',
			icon: '⧉',
			onSelect: () => editor.duplicate(menu!.blockId)
		});
		items.push({
			label: 'Delete',
			icon: '🗑',
			danger: true,
			onSelect: () => editor.remove(menu!.blockId)
		});
		return items;
	}

	// Wikilink clicks: navigate to a resolved doc, or create one for a broken link.
	async function onEditorClick(event: MouseEvent) {
		const el = (event.target as HTMLElement).closest('.wikilink');
		if (!el) return;
		event.preventDefault();
		const href = el.getAttribute('href');
		if (href) {
			goto(href);
			return;
		}
		const title = el.getAttribute('data-wikilink');
		if (!title) return;
		const created = await documentTree.create(title);
		await linkIndex.refresh();
		goto(`/w/${created.workspace_id}/d/${created.id}`);
	}

	function peerOn(blockId: string) {
		return editor.peers.find((peer) => peer.block_id === blockId) ?? null;
	}

	function onKeydown(event: KeyboardEvent) {
		const meta = event.metaKey || event.ctrlKey;
		if (!meta) return;
		const key = event.key.toLowerCase();
		// Cmd/Ctrl+Z = undo; Cmd/Ctrl+Shift+Z or Ctrl+Y = redo.
		const isRedo = (key === 'z' && event.shiftKey) || key === 'y';
		const isUndo = key === 'z' && !event.shiftKey;
		if (!isUndo && !isRedo) return;
		event.preventDefault();
		if (isRedo) editor.redo();
		else editor.undo();
	}
</script>

<svelte:window onkeydown={onKeydown} />

<!-- svelte-ignore a11y_no_static_element_interactions, a11y_click_events_have_key_events -->
<div class="editor" data-testid="block-editor" onclick={onEditorClick}>
	{#each editor.blocks as block (block.id)}
		{@const definition = blockDefinition(block.type)}
		{@const peer = peerOn(block.id)}
		<div
			class="row"
			class:focused={editor.focusedId === block.id}
			style:--peer-color={peer ? peer.color : 'transparent'}
			data-block-id={block.id}
			data-block-type={block.type}
		>
			<div class="gutter">
				<button
					class="gutter-btn"
					title="Add block below"
					aria-label="Add block below"
					onclick={() => editor.insertAfter(block.id, 'paragraph')}>＋</button
				>
				<button
					class="gutter-btn"
					title="Move up"
					aria-label="Move up"
					onclick={() => editor.move(block.id, -1)}>↑</button
				>
				<button
					class="gutter-btn"
					title="Move down"
					aria-label="Move down"
					onclick={() => editor.move(block.id, 1)}>↓</button
				>
				{#if sharing}
					<button
						class="gutter-btn"
						class:has-comments={sharing.commentsFor(block.id).length > 0}
						title="Comments"
						aria-label="Comments"
						data-testid="block-comments"
						onclick={() => (commentsFor = commentsFor === block.id ? null : block.id)}
						>💬</button
					>
				{/if}
				<button
					class="gutter-btn danger"
					title="Delete block"
					aria-label="Delete block"
					data-testid="block-delete"
					onclick={() => editor.remove(block.id)}>🗑</button
				>
			</div>
			<!-- svelte-ignore a11y_no_static_element_interactions -->
			<div
				class="body"
				class:peered={peer !== null}
				oncontextmenu={(event) => onContextMenu(event, block)}
			>
				{#if peer}
					<span class="peer-label" style:background={peer.color}>{peer.user_id}</span>
				{/if}
				{#if definition}
					<definition.component {block} {editor} />
				{:else}
					<div class="unknown">Unsupported block type: {block.type}</div>
				{/if}
				{#if editor.slashFor === block.id}
					<SlashMenu {editor} />
				{/if}
				{#if editor.linkFor === block.id}
					<LinkMenu {editor} />
				{/if}
				{#if sharing && commentsFor === block.id}
					<CommentThread {sharing} blockId={block.id} onclose={() => (commentsFor = null)} />
				{/if}
			</div>
		</div>
	{/each}

	<button
		class="tail"
		data-testid="append-block"
		onclick={() => editor.insertAfter(null, 'paragraph')}
	>
		＋ Add a block
	</button>
</div>

{#if menu}
	<ContextMenu x={menu.x} y={menu.y} items={menuItems()} onclose={() => (menu = null)} />
{/if}

<style>
	.editor {
		display: flex;
		flex-direction: column;
		gap: 2px;
		padding-bottom: 32px;
	}
	.row {
		display: flex;
		gap: 4px;
		border-radius: var(--r-control);
		/* Extend the row's hover box left to house the gutter, with no dead gap
		 * between the text and the buttons — otherwise the mouse loses :hover on
		 * the way over and the gutter vanishes before it can be clicked. The
		 * negative margin keeps the body visually in the same column. */
		position: relative;
		padding-left: 126px;
		margin-left: -126px;
	}
	.gutter {
		position: absolute;
		left: 4px;
		top: 0;
		display: flex;
		gap: 1px;
		visibility: hidden;
		align-items: flex-start;
		padding-top: 5px;
		/* Fits add / up / down / comments / delete without overflowing. */
		width: 118px;
		justify-content: flex-end;
	}
	.row:hover .gutter {
		visibility: visible;
	}
	.gutter-btn {
		color: var(--tx3);
		padding: 1px 5px;
		border-radius: 4px;
		font-size: 12px;
	}
	.gutter-btn:hover {
		background: var(--bg2);
		color: var(--tx);
	}
	.gutter-btn.has-comments {
		visibility: visible;
		color: var(--acc);
	}
	.gutter-btn.danger:hover {
		background: var(--aibg);
		color: var(--rose);
	}
	.body {
		flex: 1;
		position: relative;
		padding: 3px 6px;
		border-radius: var(--r-control);
		min-width: 0;
	}
	.body.peered {
		box-shadow: inset 0 0 0 2px var(--peer-color);
	}
	.peer-label {
		position: absolute;
		top: -9px;
		right: 6px;
		color: #fff;
		font-size: 9px;
		padding: 1px 6px;
		border-radius: var(--r-pill);
		max-width: 140px;
		overflow: hidden;
		text-overflow: ellipsis;
		z-index: 5;
	}
	.unknown {
		color: var(--tx3);
		font-style: italic;
	}
	.tail {
		text-align: left;
		color: var(--tx3);
		padding: 6px;
		border-radius: var(--r-control);
	}
	.tail:hover {
		background: var(--bg2);
		color: var(--tx);
	}
</style>
