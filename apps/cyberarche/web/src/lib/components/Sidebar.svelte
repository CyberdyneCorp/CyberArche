<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { documentTree } from '$lib/viewmodels/document-tree.svelte';
	import { session } from '$lib/viewmodels/session.svelte';
	import type { TeamspacesVM } from '$lib/viewmodels/teamspaces.svelte';
	import { theme } from '$lib/viewmodels/theme.svelte';
	import TreeItem from './TreeItem.svelte';
	import WorkspaceSwitcher from './WorkspaceSwitcher.svelte';

	let {
		workspaceId,
		teamspaces
	}: { workspaceId: string; teamspaces: TeamspacesVM | null } = $props();

	let creatingTeamspace = $state(false);
	let teamspaceName = $state('');

	async function newDocument(teamspaceId?: string) {
		const document = await documentTree.create('', undefined, teamspaceId);
		if (teamspaceId) await teamspaces?.reload(teamspaceId);
		await goto(`/w/${workspaceId}/d/${document.id}`);
	}

	async function newFolder(teamspaceId: string | null) {
		if (!teamspaces) return;
		const name = prompt('Folder name')?.trim();
		if (name) await teamspaces.createFolder(name, teamspaceId);
	}

	async function newDocumentInFolder(folder: {
		id: string;
		teamspace_id: string | null;
	}) {
		// Create the doc in the folder's scope, then group it under the folder.
		const document = await documentTree.create(
			'',
			undefined,
			folder.teamspace_id ?? undefined
		);
		const { placeInFolder } = await import('$lib/api/folders');
		await placeInFolder(document.id, folder.id);
		await teamspaces?.reloadFolder(folder.id);
		await goto(`/w/${workspaceId}/d/${document.id}`);
	}

	async function createTeamspace(event: SubmitEvent) {
		event.preventDefault();
		const name = teamspaceName.trim();
		if (!name || !teamspaces) return;
		await teamspaces.create(name);
		teamspaceName = '';
		creatingTeamspace = false;
	}

	async function confirmPurge(id: string, title: string) {
		// Permanent and unrecoverable — confirm before purging.
		if (!confirm(`Permanently delete "${title || 'Untitled'}"? This cannot be undone.`)) {
			return;
		}
		await documentTree.purge(id);
	}

	async function signOut() {
		session.logout();
		await goto('/signin');
	}

	const docHref = (id: string) => `/w/${workspaceId}/d/${id}`;

	const privateRoots = $derived(
		documentTree.roots.filter(
			(n) => !n.document.teamspace_id && !n.document.folder_id
		)
	);
	const privateEmpty = $derived(
		privateRoots.length === 0 && (teamspaces?.foldersFor(null).length ?? 0) === 0
	);
</script>

<aside class="sidebar">
	<WorkspaceSwitcher {workspaceId} />

	<button class="new" data-testid="new-document" onclick={() => newDocument()}>
		<span class="plus">＋</span> New document
	</button>

	{#if teamspaces && teamspaces.favorites.length > 0}
		<nav class="section">
			<h2>Favorites</h2>
			{#each teamspaces.favorites as doc (doc.id)}
				<a
					class="row"
					class:active={page.url.pathname === docHref(doc.id)}
					href={docHref(doc.id)}
					data-testid="favorite-doc"
				>
					<span class="icon">★</span>
					<span class="title">{doc.title}</span>
				</a>
			{/each}
		</nav>
	{/if}

	{#if teamspaces}
		<nav class="section">
			<div class="section-head">
				<h2>Teamspaces</h2>
				<button
					class="section-add"
					title="New teamspace"
					aria-label="New teamspace"
					data-testid="new-teamspace"
					onclick={() => (creatingTeamspace = !creatingTeamspace)}>＋</button
				>
			</div>

			{#if creatingTeamspace}
				<form class="inline-create" onsubmit={createTeamspace}>
					<!-- svelte-ignore a11y_autofocus -->
					<input
						class="input"
						placeholder="Teamspace name"
						bind:value={teamspaceName}
						autofocus
						data-testid="teamspace-name"
					/>
				</form>
			{/if}

			{#each teamspaces.nodes as node (node.teamspace.id)}
				<div class="row group" data-testid="teamspace-row">
					<button
						class="disclosure"
						aria-label={node.expanded ? 'Collapse' : 'Expand'}
						onclick={() => teamspaces!.toggle(node.teamspace.id)}
						>{node.expanded ? '▾' : '▸'}</button
					>
					<span class="ts-icon">{node.teamspace.icon}</span>
					<span class="title" data-testid="teamspace-name-label">{node.teamspace.name}</span>
					<button
						class="row-add"
						title="New folder"
						aria-label="New folder"
						data-testid="teamspace-add-folder"
						onclick={() => newFolder(node.teamspace.id)}>📁</button
					>
					<button
						class="row-add"
						title="Add a page"
						aria-label="Add a page"
						data-testid="teamspace-add-page"
						onclick={() => newDocument(node.teamspace.id)}>＋</button
					>
				</div>
				{#if node.expanded}
					{@render folderList(node.teamspace.id)}
					{#each node.documents as doc (doc.id)}
						<a
							class="row nested"
							class:active={page.url.pathname === docHref(doc.id)}
							href={docHref(doc.id)}
							data-testid="teamspace-doc"
						>
							<span class="icon">▤</span>
							<span class="title">{doc.title}</span>
						</a>
					{:else}
						<p class="empty nested">No pages yet</p>
					{/each}
				{/if}
			{:else}
				{#if !creatingTeamspace}
					<p class="empty" data-testid="no-teamspaces">No teamspaces yet</p>
				{/if}
			{/each}
		</nav>
	{/if}

	<nav class="section grow">
		<div class="section-head">
			<h2>Private</h2>
			{#if teamspaces}
				<button
					class="section-add"
					title="New folder"
					aria-label="New private folder"
					data-testid="private-add-folder"
					onclick={() => newFolder(null)}>📁</button
				>
			{/if}
		</div>
		<div class="tree" data-testid="document-tree">
			{#if teamspaces}
				{@render folderList(null)}
			{/if}
			{#each documentTree.roots as node (node.document.id)}
				{#if !node.document.teamspace_id && !node.document.folder_id}
					<TreeItem {node} {teamspaces} />
				{/if}
			{/each}
			{#if privateEmpty}
				<p class="empty">Nothing private yet</p>
			{/if}
		</div>
	</nav>

{#snippet folderList(scope: string | null)}
	{#each teamspaces?.foldersFor(scope) ?? [] as fn (fn.folder.id)}
		<div class="row group" data-testid="folder-row">
			<button
				class="disclosure"
				aria-label={fn.expanded ? 'Collapse' : 'Expand'}
				onclick={() => teamspaces!.toggleFolder(fn.folder.id)}
				>{fn.expanded ? '▾' : '▸'}</button
			>
			<span class="ts-icon">📁</span>
			<span class="title" data-testid="folder-name">{fn.folder.name}</span>
			<button
				class="row-add"
				title="Add a page"
				aria-label="Add a page to folder"
				data-testid="folder-add-page"
				onclick={() => newDocumentInFolder(fn.folder)}>＋</button
			>
		</div>
		{#if fn.expanded}
			{#each fn.documents as doc (doc.id)}
				<a
					class="row nested"
					class:active={page.url.pathname === docHref(doc.id)}
					href={docHref(doc.id)}
					data-testid="folder-doc"
				>
					<span class="icon">▤</span>
					<span class="title">{doc.title}</span>
				</a>
			{:else}
				<p class="empty nested">No pages yet</p>
			{/each}
		{/if}
	{/each}
{/snippet}

	<!-- Documents reachable only through a direct grant: they belong to a
	     workspace or teamspace the user is not a member of, so they cannot
	     appear in the tree above. -->
	{#if teamspaces && teamspaces.shared.length > 0}
		<nav class="section">
			<h2>Shared with me</h2>
			{#each teamspaces.shared as doc (doc.id)}
				<a
					class="row"
					class:active={page.url.pathname === docHref(doc.id)}
					href={docHref(doc.id)}
					data-testid="shared-doc"
				>
					<span class="icon">👤</span>
					<span class="title">{doc.title}</span>
				</a>
			{/each}
		</nav>
	{/if}

	{#if documentTree.trash.length > 0}
		<nav class="section">
			<h2>Trash</h2>
			{#each documentTree.trash as doc (doc.id)}
				<div class="trash-row" data-testid="trash-doc">
					<span class="title">{doc.title}</span>
					<button data-testid="trash-restore" onclick={() => documentTree.restore(doc.id)}
						>Restore</button
					>
					<button
						class="danger"
						data-testid="trash-purge"
						title="Delete permanently"
						onclick={() => confirmPurge(doc.id, doc.title)}>Delete</button
					>
				</div>
			{/each}
		</nav>
	{/if}

	<footer class="footer">
		<a class="foot-btn" href={`/w/${workspaceId}/settings`} data-testid="open-settings">
			⚙ Settings &amp; connectors
		</a>
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
		overflow: hidden;
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
		margin-top: 8px;
		overflow-y: auto;
		flex-shrink: 0;
	}
	.section.grow {
		flex: 1;
		min-height: 60px;
	}
	.section-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}
	.section h2 {
		margin: 6px;
		font-size: 10px;
		font-weight: 600;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--tx3);
	}
	.section-add,
	.row-add {
		color: var(--tx3);
		padding: 2px 6px;
		border-radius: 4px;
		font-size: 12px;
	}
	.section-add:hover,
	.row-add:hover {
		background: var(--bg2);
		color: var(--tx);
	}
	.row {
		display: flex;
		align-items: center;
		gap: 6px;
		padding: 4px 6px;
		border-radius: var(--r-control);
		color: var(--tx);
		text-decoration: none;
		min-width: 0;
	}
	.row:hover {
		background: var(--bg2);
	}
	.row.active {
		background: var(--accbg);
		color: var(--acc-strong);
		font-weight: 500;
	}
	.row.nested {
		padding-left: 26px;
	}
	.row.group .row-add {
		visibility: hidden;
	}
	.row.group:hover .row-add {
		visibility: visible;
	}
	.disclosure {
		width: 14px;
		color: var(--tx3);
		font-size: 9px;
	}
	.ts-icon {
		display: grid;
		place-items: center;
		width: 16px;
		height: 16px;
		border-radius: 4px;
		background: var(--rose);
		color: #fff;
		font-size: 9px;
		font-weight: 700;
	}
	.icon {
		color: var(--tx3);
		font-size: 11px;
	}
	.title {
		flex: 1;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.inline-create {
		padding: 2px 6px 6px;
	}
	.inline-create .input {
		width: 100%;
		font-size: 12px;
	}
	.empty {
		margin: 4px 6px;
		color: var(--tx3);
	}
	.empty.nested {
		padding-left: 20px;
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
	.trash-row button.danger {
		color: var(--rose);
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
		text-decoration: none;
		display: block;
	}
	.foot-btn:hover {
		background: var(--bg2);
		color: var(--tx);
	}
</style>
