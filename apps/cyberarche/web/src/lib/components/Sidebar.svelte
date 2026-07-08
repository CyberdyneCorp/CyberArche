<script lang="ts">
	import { goto } from '$app/navigation';
	import { documentTree } from '$lib/viewmodels/document-tree.svelte';
	import { session } from '$lib/viewmodels/session.svelte';
	import { theme } from '$lib/viewmodels/theme.svelte';
	import { workspaces } from '$lib/viewmodels/workspaces.svelte';
	import TreeItem from './TreeItem.svelte';

	let { workspaceId }: { workspaceId: string } = $props();

	const workspace = $derived(workspaces.byId(workspaceId));
	const initials = $derived(
		(workspace?.name ?? 'CA')
			.split(/\s+/)
			.map((part) => part[0])
			.join('')
			.slice(0, 2)
			.toUpperCase()
	);

	async function newDocument() {
		const document = await documentTree.create('');
		await goto(`/w/${workspaceId}/d/${document.id}`);
	}

	async function signOut() {
		session.logout();
		await goto('/signin');
	}
</script>

<aside class="sidebar">
	<header class="workspace">
		<div class="mark">{initials}</div>
		<div class="meta">
			<strong data-testid="workspace-name">{workspace?.name ?? '…'}</strong>
		</div>
	</header>

	<button class="new" data-testid="new-document" onclick={newDocument}>
		<span class="plus">＋</span> New document
	</button>

	<nav class="section">
		<h2>Documents</h2>
		<div class="tree" data-testid="document-tree">
			{#each documentTree.roots as node (node.document.id)}
				<TreeItem {node} />
			{/each}
			{#if documentTree.roots.length === 0}
				<p class="empty">No documents yet</p>
			{/if}
		</div>
	</nav>

	{#if documentTree.trash.length > 0}
		<nav class="section">
			<h2>Trash</h2>
			{#each documentTree.trash as doc (doc.id)}
				<div class="trash-row" data-testid="trash-doc">
					<span class="title">{doc.title}</span>
					<button onclick={() => documentTree.restore(doc.id)}>Restore</button>
				</div>
			{/each}
		</nav>
	{/if}

	<footer class="footer">
		<button class="foot-btn" onclick={() => theme.toggle()} data-testid="theme-toggle">
			◐ {theme.mode === 'dark' ? 'Light' : 'Dark'} theme
		</button>
		<button class="foot-btn" onclick={signOut} data-testid="sign-out">↩ Sign out</button>
	</footer>
</aside>

<style>
	.sidebar {
		display: flex;
		flex-direction: column;
		width: 248px;
		min-width: 248px;
		height: 100vh;
		background: var(--bg0);
		border-right: 1px solid var(--line);
		padding: 10px;
	}
	.workspace {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 6px;
	}
	.mark {
		display: grid;
		place-items: center;
		width: 26px;
		height: 26px;
		border-radius: 7px;
		background: var(--tx);
		color: var(--bg1);
		font-size: 10.5px;
		font-weight: 700;
	}
	.new {
		display: flex;
		align-items: center;
		gap: 6px;
		margin: 8px 0;
		padding: 6px 8px;
		border-radius: var(--r-control);
		color: var(--acc-strong);
		font-weight: 500;
	}
	.new:hover {
		background: var(--accbg);
	}
	.plus {
		font-size: 12px;
	}
	.section {
		margin-top: 10px;
		overflow-y: auto;
	}
	.section h2 {
		margin: 6px;
		font-size: 10px;
		font-weight: 600;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--tx3);
	}
	.empty {
		margin: 4px 6px;
		color: var(--tx3);
	}
	.trash-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 3px 6px;
		color: var(--tx2);
	}
	.trash-row .title {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.trash-row button {
		color: var(--acc-strong);
		font-size: 11px;
	}
	.footer {
		margin-top: auto;
		border-top: 1px solid var(--line);
		padding-top: 8px;
		display: flex;
		flex-direction: column;
		gap: 2px;
	}
	.foot-btn {
		text-align: left;
		padding: 5px 6px;
		border-radius: var(--r-control);
		color: var(--tx2);
	}
	.foot-btn:hover {
		background: var(--bg2);
		color: var(--tx);
	}
</style>
