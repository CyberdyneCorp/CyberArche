<script lang="ts">
	import type { TreeNode } from '$lib/viewmodels/document-tree.svelte';
	import { documentTree } from '$lib/viewmodels/document-tree.svelte';
	import type { TeamspacesVM } from '$lib/viewmodels/teamspaces.svelte';
	import { page } from '$app/state';
	import TreeItem from './TreeItem.svelte';

	let {
		node,
		depth = 0,
		teamspaces = null
	}: { node: TreeNode; depth?: number; teamspaces?: TeamspacesVM | null } = $props();

	const href = $derived(`/w/${node.document.workspace_id}/d/${node.document.id}`);
	const active = $derived(page.url.pathname === href);
</script>

<div class="item" style="--depth: {depth}">
	<button
		class="disclosure"
		aria-label={node.expanded ? 'Collapse' : 'Expand'}
		onclick={() => documentTree.toggle(node.document.id)}
	>
		{node.expanded ? '▾' : '▸'}
	</button>
	<a class="doc" class:active {href} data-testid="tree-doc">
		<span class="icon">▤</span>
		<span class="title">{node.document.title}</span>
	</a>
	<span class="actions">
		{#if teamspaces}
			<button
				class:favorited={teamspaces.isFavorite(node.document.id)}
				title={teamspaces.isFavorite(node.document.id) ? 'Remove favourite' : 'Favourite'}
				aria-label="Toggle favourite"
				data-testid="favorite-toggle"
				onclick={() => teamspaces!.toggleFavorite(node.document)}
				>{teamspaces.isFavorite(node.document.id) ? '★' : '☆'}</button
			>
		{/if}
		<button
			title="Add child document"
			aria-label="Add child document"
			onclick={() => documentTree.create('', node.document.id)}>＋</button
		>
		<button
			title="Move to trash"
			aria-label="Move to trash"
			onclick={() => documentTree.moveToTrash(node.document.id)}>🗑</button
		>
	</span>
</div>

{#if node.expanded}
	{#each node.children as child (child.document.id)}
		<TreeItem node={child} depth={depth + 1} {teamspaces} />
	{/each}
{/if}

<style>
	.item {
		display: flex;
		align-items: center;
		gap: 2px;
		padding-left: calc(6px + var(--depth) * 14px);
		border-radius: var(--r-control);
	}
	.item:hover {
		background: var(--bg2);
	}
	.item:hover .actions {
		visibility: visible;
	}
	.disclosure {
		width: 16px;
		color: var(--tx3);
		font-size: 9px;
		padding: 2px 0;
	}
	.doc {
		flex: 1;
		display: flex;
		align-items: center;
		gap: 6px;
		padding: 4px 6px;
		color: var(--tx);
		text-decoration: none;
		border-radius: var(--r-control);
		min-width: 0;
	}
	.doc.active {
		background: var(--accbg);
		color: var(--acc-strong);
		font-weight: 500;
	}
	.icon {
		color: var(--tx3);
		font-size: 11px;
	}
	.title {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.actions {
		visibility: hidden;
		display: flex;
		gap: 2px;
		padding-right: 4px;
	}
	.actions button {
		padding: 2px 4px;
		border-radius: 4px;
		color: var(--tx3);
		font-size: 11px;
	}
	.actions button:hover {
		background: var(--bg3);
		color: var(--tx);
	}
	.actions button.favorited {
		visibility: visible;
		color: var(--acc);
	}
</style>
