<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { documentTree } from '$lib/viewmodels/document-tree.svelte';
	import {
		createCollectionList,
		type CollectionListVM
	} from '$lib/viewmodels/collection.svelte';
	import { dialogs } from '$lib/viewmodels/dialogs.svelte';
	import { docTitles } from '$lib/viewmodels/doc-titles';
	import { graphView } from '$lib/viewmodels/graph-view.svelte';
	import { session } from '$lib/viewmodels/session.svelte';
	import type { TeamspaceNode, FolderNode, TeamspacesVM } from '$lib/viewmodels/teamspaces.svelte';
	import { commandPalette } from '$lib/viewmodels/commandPalette.svelte';
	import { settingsModal } from '$lib/viewmodels/settingsModal.svelte';
	import { workspaceChatOpen } from '$lib/viewmodels/workspaceChat.svelte';
	import { meetingNotesModal } from '$lib/viewmodels/meetingNotesModal.svelte';
	import { importDocuments, IMPORT_ACCEPT } from '$lib/viewmodels/import-documents';
	import { theme } from '$lib/viewmodels/theme.svelte';
	import { toasts } from '$lib/viewmodels/toasts.svelte';
	import ContextMenu from './ContextMenu.svelte';
	import NotificationsBell from './NotificationsBell.svelte';
	import TeamspaceMembersDialog from './TeamspaceMembersDialog.svelte';
	import TemplatePicker from './TemplatePicker.svelte';
	import TreeItem from './TreeItem.svelte';
	import WorkspaceSwitcher from './WorkspaceSwitcher.svelte';

	let {
		workspaceId,
		teamspaces
	}: { workspaceId: string; teamspaces: TeamspacesVM | null } = $props();

	let creatingTeamspace = $state(false);
	let teamspaceName = $state('');

	let collectionsVM = $state<CollectionListVM | null>(null);
	$effect(() => {
		const vm = createCollectionList(workspaceId);
		collectionsVM = vm;
		vm.load();
	});

	async function newCollection() {
		const name = (
			await dialogs.prompt({
				title: 'New collection',
				placeholder: 'Collection name',
				confirmLabel: 'Create'
			})
		)?.trim();
		if (!name || !collectionsVM) return;
		const collection = await collectionsVM.create(name);
		if (collection) await goto(`/w/${workspaceId}/c/${collection.id}`);
		else toasts.error(collectionsVM.error ?? "Couldn't create collection");
	}

	const collectionHref = (id: string) => `/w/${workspaceId}/c/${id}`;

	async function newDocument(teamspaceId?: string) {
		const document = await documentTree.create('', undefined, teamspaceId);
		if (teamspaceId) await teamspaces?.reload(teamspaceId);
		await goto(`/w/${workspaceId}/d/${document.id}`);
	}

	let importInput = $state<HTMLInputElement | null>(null);

	async function onImportPick(event: Event) {
		const input = event.currentTarget as HTMLInputElement;
		const file = input.files?.[0];
		input.value = ''; // allow re-picking the same file
		if (!file) return;
		try {
			const first = await importDocuments(workspaceId, file);
			if (first) await goto(`/w/${workspaceId}/d/${first.id}`);
			else toasts.error('That file had no importable content.');
		} catch {
			toasts.error("Couldn't import that file.");
		}
	}

	async function newFolder(teamspaceId: string | null) {
		if (!teamspaces) return;
		const name = (
			await dialogs.prompt({
				title: 'New folder',
				placeholder: 'Folder name',
				confirmLabel: 'Create'
			})
		)?.trim();
		if (!name) return;
		const folder = await teamspaces.createFolder(name, teamspaceId);
		if (folder) toasts.success(`Created folder “${name}”`);
		else toasts.error(teamspaces.error ?? "Couldn't create folder");
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
		const ok = await dialogs.confirm({
			title: 'Delete permanently',
			message: `Permanently delete “${title || 'Untitled'}”? This cannot be undone.`,
			confirmLabel: 'Delete forever',
			danger: true
		});
		if (!ok) return;
		await documentTree.purge(id);
		toasts.success('Deleted permanently');
	}

	async function restoreAllTrash() {
		const ids = documentTree.trash.map((d) => d.id);
		if (ids.length === 0) return;
		for (const id of ids) await documentTree.restore(id);
		await refresh();
		toasts.success(ids.length === 1 ? 'Restored 1 document' : `Restored ${ids.length} documents`);
	}

	async function emptyTrash() {
		const ids = documentTree.trash.map((d) => d.id);
		if (ids.length === 0) return;
		const ok = await dialogs.confirm({
			title: 'Empty trash',
			message: `Permanently delete ${
				ids.length === 1 ? 'this document' : `all ${ids.length} documents`
			} in the trash? This cannot be undone.`,
			confirmLabel: 'Delete all',
			danger: true
		});
		if (!ok) return;
		for (const id of ids) await documentTree.purge(id);
		toasts.success('Trash emptied');
	}

	async function signOut() {
		session.logout();
		await goto('/signin');
	}

	const docHref = (id: string) => `/w/${workspaceId}/d/${id}`;

	// --- drag documents into a teamspace / folder / private -------------------
	let dropTarget = $state<string | null>(null); // id of the hovered target

	async function refresh() {
		await Promise.all([teamspaces?.load(), documentTree.open(workspaceId)]);
	}

	// --- context menu + delete flows ------------------------------------------
	interface MenuItem {
		label: string;
		danger?: boolean;
		testid?: string;
		onSelect: () => void;
	}
	let menu = $state<{ x: number; y: number; items: MenuItem[] } | null>(null);

	function onKebab(event: MouseEvent, items: MenuItem[]) {
		const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
		menu = { x: rect.left, y: rect.bottom + 4, items };
	}

	function onContext(event: MouseEvent, items: MenuItem[]) {
		event.preventDefault();
		menu = { x: event.clientX, y: event.clientY, items };
	}

	const teamspaceMenu = (node: TeamspaceNode): MenuItem[] => [
		{
			label: 'Open graph',
			testid: 'teamspace-graph',
			onSelect: () =>
				graphView.open({
					kind: 'teamspace',
					id: node.teamspace.id,
					name: node.teamspace.name
				})
		},
		{
			label: 'Manage members',
			testid: 'teamspace-members',
			onSelect: () => (membersFor = node)
		},
		{
			label: 'Export (ZIP)',
			testid: 'teamspace-export',
			onSelect: () => exportTeamspaceFlow(node)
		},
		{
			label: 'Delete teamspace',
			danger: true,
			testid: 'teamspace-delete',
			onSelect: () => deleteTeamspaceFlow(node)
		}
	];

	const folderMenu = (fn: FolderNode): MenuItem[] => [
		{
			label: 'Open graph',
			testid: 'folder-graph',
			onSelect: () =>
				graphView.open({ kind: 'folder', id: fn.folder.id, name: fn.folder.name })
		},
		{
			label: 'Export (ZIP)',
			testid: 'folder-export',
			onSelect: () => exportFolderFlow(fn)
		},
		{
			label: 'Delete folder',
			danger: true,
			testid: 'folder-delete',
			onSelect: () => deleteFolderFlow(fn)
		}
	];

	let membersFor = $state<TeamspaceNode | null>(null);
	let templatePickerOpen = $state(false);

	async function exportTeamspaceFlow(node: TeamspaceNode) {
		const { teamspaceDocuments } = await import('$lib/api/teamspaces');
		const { exportScopeZip } = await import('$lib/editor/zip-export');
		try {
			const docs = await teamspaceDocuments(node.teamspace.id);
			if (!docs.length) return toasts.error('No documents to export');
			toasts.success(`Exporting ${docs.length} document${docs.length > 1 ? 's' : ''}…`);
			const n = await exportScopeZip(node.teamspace.name, docs);
			toasts.success(`Exported ${n} document${n === 1 ? '' : 's'}`);
		} catch {
			toasts.error(`Couldn't export “${node.teamspace.name}”`);
		}
	}

	async function exportFolderFlow(fn: FolderNode) {
		const { folderDocuments } = await import('$lib/api/folders');
		const { exportScopeZip } = await import('$lib/editor/zip-export');
		try {
			const docs = await folderDocuments(fn.folder.id);
			if (!docs.length) return toasts.error('No documents to export');
			toasts.success(`Exporting ${docs.length} document${docs.length > 1 ? 's' : ''}…`);
			const n = await exportScopeZip(fn.folder.name, docs);
			toasts.success(`Exported ${n} document${n === 1 ? '' : 's'}`);
		} catch {
			toasts.error(`Couldn't export “${fn.folder.name}”`);
		}
	}

	function docsPhrase(count: number): string {
		if (count <= 0) return 'no documents';
		return count === 1 ? 'its 1 document' : `its ${count} documents`;
	}

	async function deleteTeamspaceFlow(node: TeamspaceNode) {
		const ts = node.teamspace;
		let count = node.documents.length;
		const { teamspaceDocuments, deleteTeamspace } = await import('$lib/api/teamspaces');
		try {
			count = (await teamspaceDocuments(ts.id)).length;
		} catch {
			/* fall back to the loaded count */
		}
		const ok = await dialogs.confirm({
			title: 'Delete teamspace',
			message: `Delete “${ts.name}” and move ${docsPhrase(count)} to Trash? Its folders will be removed.`,
			confirmLabel: 'Delete',
			danger: true
		});
		if (!ok) return;
		try {
			await deleteTeamspace(ts.id);
			toasts.success(`Deleted “${ts.name}”`);
			await refresh();
		} catch {
			toasts.error(`Couldn't delete “${ts.name}”`);
		}
	}

	async function deleteFolderFlow(fn: FolderNode) {
		const folder = fn.folder;
		const { folderDocuments, deleteFolder } = await import('$lib/api/folders');
		let count = fn.documents.length;
		try {
			count = (await folderDocuments(folder.id)).length;
		} catch {
			/* fall back to the loaded count */
		}
		const ok = await dialogs.confirm({
			title: 'Delete folder',
			message: `Delete folder “${folder.name}” and move ${docsPhrase(count)} to Trash?`,
			confirmLabel: 'Delete',
			danger: true
		});
		if (!ok) return;
		try {
			await deleteFolder(folder.id);
			toasts.success(`Deleted “${folder.name}”`);
			await refresh();
		} catch {
			toasts.error(`Couldn't delete “${folder.name}”`);
		}
	}

	function onDragStart(event: DragEvent, docId: string) {
		event.dataTransfer?.setData('text/doc-id', docId);
		if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move';
	}

	function allowDrop(event: DragEvent, target: string) {
		event.preventDefault();
		dropTarget = target;
	}

	async function onDrop(
		event: DragEvent,
		dest: { teamspaceId?: string; folderId?: string }
	) {
		event.preventDefault();
		dropTarget = null;
		const docId = event.dataTransfer?.getData('text/doc-id');
		if (!docId) return;
		const { placeInFolder, moveToTeamspace, moveToPrivate } = await import(
			'$lib/api/folders'
		);
		if (dest.folderId) await placeInFolder(docId, dest.folderId);
		else if (dest.teamspaceId) await moveToTeamspace(docId, dest.teamspaceId);
		else await moveToPrivate(docId);
		await refresh();
	}

	async function starDoc(doc: { id: string; title: string }) {
		await teamspaces?.toggleFavorite(doc as never);
	}

	async function trashDoc(id: string) {
		const { trashDocument } = await import('$lib/api/documents');
		await trashDocument(id);
		await refresh();
	}

	async function addChild(doc: {
		id: string;
		teamspace_id?: string | null;
		folder_id?: string | null;
	}) {
		const child = await documentTree.create(
			'',
			doc.id,
			doc.teamspace_id ?? undefined
		);
		if (doc.folder_id) {
			const { placeInFolder } = await import('$lib/api/folders');
			await placeInFolder(child.id, doc.folder_id);
		}
		await refresh();
		await goto(docHref(child.id));
	}

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

	<div class="new-row">
		<button class="new" data-testid="new-document" onclick={() => newDocument()}>
			<span class="plus">＋</span> New document
		</button>
		<button
			class="new tmpl-btn"
			data-testid="new-from-template"
			title="New from template"
			aria-label="New from template"
			onclick={() => (templatePickerOpen = true)}>▤</button
		>
		<button
			class="new tmpl-btn"
			data-testid="import-document"
			title="Import from Markdown, Word, or Notion export"
			aria-label="Import document"
			onclick={() => importInput?.click()}>⬆</button
		>
		<input
			bind:this={importInput}
			type="file"
			accept={IMPORT_ACCEPT}
			class="hidden-file"
			data-testid="import-file-input"
			onchange={onImportPick}
		/>
	</div>

	<button
		class="chat-btn search-btn"
		data-testid="open-search"
		onclick={() => commandPalette.open()}
	>
		<span aria-hidden="true">🔍</span> Search
		<kbd class="kbd">⌘K</kbd>
	</button>

	<button
		class="chat-btn"
		data-testid="open-workspace-chat"
		onclick={() => workspaceChatOpen.open()}
	>
		<span aria-hidden="true">💬</span> Chat with workspace
	</button>

	<button
		class="chat-btn"
		data-testid="open-meeting-notes"
		onclick={() => meetingNotesModal.open()}
	>
		<span aria-hidden="true">🎙️</span> Meeting notes
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
					<span class="title">{docTitles.titleOf(doc)}</span>
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
				<div
					class="row group"
					class:drop-target={dropTarget === `ts:${node.teamspace.id}`}
					data-testid="teamspace-row"
					role="group"
					ondragover={(e) => allowDrop(e, `ts:${node.teamspace.id}`)}
					ondragleave={() => (dropTarget = null)}
					ondrop={(e) => onDrop(e, { teamspaceId: node.teamspace.id })}
					oncontextmenu={(e) => onContext(e, teamspaceMenu(node))}
				>
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
					<button
						class="row-add"
						title="Teamspace actions"
						aria-label="Teamspace actions"
						data-testid="teamspace-menu"
						onclick={(e) => onKebab(e, teamspaceMenu(node))}>⋯</button
					>
				</div>
				{#if node.expanded}
					{@render folderList(node.teamspace.id)}
					{#each node.documents.filter((d) => !d.folder_id) as doc (doc.id)}
						{@render docRow(doc, 'teamspace-doc')}
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

	<nav class="section">
		<div class="section-head">
			<h2>Collections</h2>
			<button
				class="section-add"
				title="New collection"
				aria-label="New collection"
				data-testid="new-collection"
				onclick={newCollection}>＋</button
			>
		</div>
		{#each collectionsVM?.collections ?? [] as collection (collection.id)}
			<a
				class="row"
				class:active={page.url.pathname === collectionHref(collection.id)}
				href={collectionHref(collection.id)}
				data-testid="collection-row"
			>
				<span class="icon">▦</span>
				<span class="title">{collection.name}</span>
			</a>
		{:else}
			<p class="empty" data-testid="no-collections">No collections yet</p>
		{/each}
	</nav>

	<nav
		class="section grow"
		class:drop-target={dropTarget === 'private'}
		role="region"
		aria-label="Private"
		ondragover={(e) => allowDrop(e, 'private')}
		ondragleave={() => (dropTarget = null)}
		ondrop={(e) => onDrop(e, {})}
	>
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
		<div
			class="row group"
			class:drop-target={dropTarget === `folder:${fn.folder.id}`}
			data-testid="folder-row"
			role="group"
			ondragover={(e) => allowDrop(e, `folder:${fn.folder.id}`)}
			ondragleave={() => (dropTarget = null)}
			ondrop={(e) => onDrop(e, { folderId: fn.folder.id })}
			oncontextmenu={(e) => onContext(e, folderMenu(fn))}
		>
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
			<button
				class="row-add"
				title="Folder actions"
				aria-label="Folder actions"
				data-testid="folder-menu"
				onclick={(e) => onKebab(e, folderMenu(fn))}>⋯</button
			>
		</div>
		{#if fn.expanded}
			{#each fn.documents as doc (doc.id)}
				{@render docRow(doc, 'folder-doc')}
			{:else}
				<p class="empty nested">No pages yet</p>
			{/each}
		{/if}
	{/each}
{/snippet}

{#snippet docRow(doc: import('$lib/api/documents').Document, testid: string)}
	<div
		class="row nested doc"
		class:active={page.url.pathname === docHref(doc.id)}
		role="listitem"
		draggable="true"
		ondragstart={(e) => onDragStart(e, doc.id)}
	>
		<a class="doc-link" href={docHref(doc.id)} data-testid={testid}>
			<span class="icon">▤</span>
			<span class="title">{docTitles.titleOf(doc)}</span>
		</a>
		<button
			class="row-add"
			title={teamspaces?.isFavorite(doc.id) ? 'Unfavourite' : 'Favourite'}
			aria-label="Favourite"
			data-testid="doc-star"
			onclick={() => starDoc(doc)}>{teamspaces?.isFavorite(doc.id) ? '★' : '☆'}</button
		>
		<button
			class="row-add"
			title="Add child document"
			aria-label="Add child document"
			data-testid="doc-add-child"
			onclick={() => addChild(doc)}>＋</button
		>
		<button
			class="row-add danger"
			title="Move to trash"
			aria-label="Move to trash"
			data-testid="doc-trash"
			onclick={() => trashDoc(doc.id)}>🗑</button
		>
	</div>
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
					<span class="title">{docTitles.titleOf(doc)}</span>
				</a>
			{/each}
		</nav>
	{/if}

	{#if documentTree.trash.length > 0}
		<nav class="section trash">
			<div class="section-head">
				<h2><span class="trash-icon" aria-hidden="true">🗑</span> Trash</h2>
				<div class="trash-actions">
					<button
						class="mini"
						title="Restore all documents"
						data-testid="trash-restore-all"
						onclick={restoreAllTrash}>Restore all</button
					>
					<button
						class="mini danger"
						title="Delete all permanently"
						data-testid="trash-empty"
						onclick={emptyTrash}>Delete all</button
					>
				</div>
			</div>
			<div class="trash-list">
				{#each documentTree.trash as doc (doc.id)}
					<div class="trash-row" data-testid="trash-doc">
						<span class="title">{doc.title || 'Untitled'}</span>
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
			</div>
		</nav>
	{/if}

	<footer class="footer">
		<NotificationsBell {workspaceId} />
		<button class="foot-btn" onclick={() => settingsModal.open()} data-testid="open-settings">
			⚙ Settings &amp; connectors
		</button>
		<button class="foot-btn" onclick={() => theme.toggle()} data-testid="theme-toggle">
			◐ {theme.mode === 'dark' ? 'Light' : 'Dark'} theme
		</button>
		<button class="foot-btn" onclick={signOut} data-testid="sign-out">↩ Sign out</button>
	</footer>
</aside>

{#if membersFor}
	<TeamspaceMembersDialog
		teamspaceId={membersFor.teamspace.id}
		teamspaceName={membersFor.teamspace.name}
		onclose={() => (membersFor = null)}
	/>
{/if}

{#if templatePickerOpen}
	<TemplatePicker {workspaceId} onclose={() => (templatePickerOpen = false)} />
{/if}

{#if menu}
	<ContextMenu x={menu.x} y={menu.y} items={menu.items} onclose={() => (menu = null)} />
{/if}

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
	.new-row {
		display: flex;
		align-items: center;
		gap: 4px;
		margin: 8px 0;
	}
	.new {
		display: flex;
		align-items: center;
		gap: 6px;
		flex: 1;
		padding: 6px 8px;
		border-radius: var(--r-control);
		color: var(--acc-strong);
		font-weight: 500;
	}
	.new:hover {
		background: var(--accbg);
	}
	.tmpl-btn {
		flex: 0 0 auto;
		justify-content: center;
		padding: 6px 9px;
	}
	.hidden-file {
		display: none;
	}
	.chat-btn {
		display: flex;
		align-items: center;
		gap: 6px;
		width: 100%;
		padding: 6px 8px;
		margin-bottom: 4px;
		border-radius: var(--r-control);
		color: var(--tx2);
		font-weight: 500;
		text-align: left;
	}
	.chat-btn:hover {
		background: var(--bg2);
		color: var(--tx);
	}
	.search-btn {
		align-items: center;
	}
	.kbd {
		margin-left: auto;
		font-size: 11px;
		font-family: inherit;
		color: var(--tx3);
		border: 1px solid var(--line);
		border-radius: 4px;
		padding: 1px 5px;
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
		width: 20px;
		color: var(--tx2);
		font-size: 13px;
		line-height: 1;
	}
	.disclosure:hover {
		color: var(--tx);
	}
	.drop-target {
		outline: 2px dashed var(--acc);
		outline-offset: -2px;
		border-radius: var(--r-control);
	}
	.row.doc {
		display: flex;
		align-items: center;
	}
	.row.doc .doc-link {
		display: flex;
		align-items: center;
		gap: 6px;
		flex: 1;
		min-width: 0;
	}
	.row.doc .row-add {
		visibility: hidden;
	}
	.row.doc:hover .row-add {
		visibility: visible;
	}
	.row-add.danger:hover {
		color: var(--rose);
	}
	.row.doc {
		cursor: grab;
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
	.trash h2 {
		display: flex;
		align-items: center;
		gap: 5px;
	}
	.trash-icon {
		font-size: 11px;
	}
	.trash-actions {
		display: flex;
		gap: 4px;
	}
	.mini {
		font-size: 10px;
		font-weight: 500;
		padding: 2px 6px;
		border-radius: 5px;
		color: var(--acc-strong);
	}
	.mini:hover {
		background: var(--accbg);
	}
	.mini.danger {
		color: var(--rose);
	}
	.mini.danger:hover {
		background: var(--aibg, var(--bg2));
	}
	/* Cap the trash list and let it scroll, so a large trash never pushes the
	 * footer off-screen or breaks the sidebar layout. */
	.trash-list {
		max-height: 168px;
		overflow-y: auto;
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
