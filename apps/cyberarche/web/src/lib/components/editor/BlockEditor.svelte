<script lang="ts">
	import { blockDefinition } from '$lib/editor/registry';
	import { colorFor, type EditorVM } from '$lib/viewmodels/editor.svelte';
	import SlashMenu from './SlashMenu.svelte';

	let { editor }: { editor: EditorVM } = $props();

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
		margin-left: -78px;
		width: 74px;
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
