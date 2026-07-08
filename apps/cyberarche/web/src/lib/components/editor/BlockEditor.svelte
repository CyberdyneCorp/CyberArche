<script lang="ts">
	import CommentThread from '$lib/components/CommentThread.svelte';
	import { blockDefinition } from '$lib/editor/registry';
	import { colorFor, type EditorVM } from '$lib/viewmodels/editor.svelte';
	import type { SharingVM } from '$lib/viewmodels/sharing.svelte';
	import SlashMenu from './SlashMenu.svelte';

	let { editor, sharing = null }: { editor: EditorVM; sharing?: SharingVM | null } =
		$props();

	let commentsFor = $state<string | null>(null);

	function peerOn(blockId: string) {
		return editor.peers.find((peer) => peer.block_id === blockId) ?? null;
	}

	function onKeydown(event: KeyboardEvent) {
		const meta = event.metaKey || event.ctrlKey;
		if (!meta || event.key.toLowerCase() !== 'z') return;
		event.preventDefault();
		if (event.shiftKey) editor.redo();
		else editor.undo();
	}
</script>

<svelte:window onkeydown={onKeydown} />

<div class="editor" data-testid="block-editor">
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
			<div class="body" class:peered={peer !== null}>
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
	}
	.gutter {
		display: flex;
		gap: 1px;
		visibility: hidden;
		align-items: flex-start;
		padding-top: 5px;
		/* Fits add / up / down / comments / delete without overflowing. */
		margin-left: -122px;
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
