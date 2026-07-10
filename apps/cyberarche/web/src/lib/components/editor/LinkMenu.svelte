<script lang="ts">
	import type { EditorVM } from '$lib/viewmodels/editor.svelte';

	let { editor }: { editor: EditorVM } = $props();

	let selected = $state(0);
	const matches = $derived(editor.linkMatches);
	$effect(() => {
		editor.linkQuery; // reset selection when the query changes
		selected = 0;
	});

	function onKeydown(event: KeyboardEvent) {
		if (!editor.linkFor) return;
		if (event.key === 'ArrowDown') {
			event.preventDefault();
			selected = Math.min(selected + 1, matches.length - 1);
		} else if (event.key === 'ArrowUp') {
			event.preventDefault();
			selected = Math.max(selected - 1, 0);
		} else if (event.key === 'Enter') {
			event.preventDefault();
			if (matches[selected]) editor.applyLink(matches[selected].title);
		} else if (event.key === 'Escape') {
			editor.closeLink();
		}
	}
</script>

<svelte:window onkeydown={onKeydown} />

{#if editor.linkFor}
	<div class="menu" role="menu" data-testid="link-menu">
		{#each matches as doc, index (doc.id)}
			<button
				role="menuitem"
				class:selected={index === selected}
				onmousedown={(event) => {
					event.preventDefault();
					editor.applyLink(doc.title);
				}}
			>
				<span class="icon">▤</span>
				<span class="label">{doc.title || 'Untitled'}</span>
			</button>
		{/each}
		{#if matches.length === 0}
			<p class="none">No documents match “{editor.linkQuery}”</p>
		{/if}
	</div>
{/if}

<style>
	.menu {
		position: absolute;
		z-index: 30;
		margin-top: 4px;
		min-width: 240px;
		background: var(--bg1);
		border: 1px solid var(--line);
		border-radius: var(--r-block);
		box-shadow: var(--sh2);
		padding: 4px;
		animation: rise 120ms ease-out;
	}
	@keyframes rise {
		from {
			opacity: 0;
			transform: translateY(4px);
		}
	}
	button {
		display: flex;
		align-items: center;
		gap: 10px;
		width: 100%;
		padding: 6px 8px;
		border-radius: var(--r-control);
		text-align: left;
	}
	button.selected,
	button:hover {
		background: var(--accbg);
	}
	.icon {
		color: var(--tx3);
		font-size: 11px;
	}
	.label {
		font-weight: 500;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.none {
		margin: 6px 8px;
		color: var(--tx3);
	}
</style>
