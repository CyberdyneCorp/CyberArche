<script lang="ts">
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { getDocument, getDocumentPath, type Document, type PathCrumb } from '$lib/api/documents';
	import AgentPanel from '$lib/components/AgentPanel.svelte';
	import Breadcrumb from '$lib/components/Breadcrumb.svelte';
	import BacklinksPanel from '$lib/components/BacklinksPanel.svelte';
	import BlockEditor from '$lib/components/editor/BlockEditor.svelte';
	import { registerBuiltinBlocks } from '$lib/editor/blocks';
	import ExportDialog from '$lib/components/ExportDialog.svelte';
	import HistoryModal from '$lib/components/HistoryModal.svelte';
	import ShareDialog from '$lib/components/ShareDialog.svelte';
	import { historyModal } from '$lib/viewmodels/historyModal.svelte';
	import { createAgentPanel, type AgentPanelVM } from '$lib/viewmodels/agent.svelte';
	import { createConnectors, type ConnectorsVM } from '$lib/viewmodels/connectors.svelte';
	import { documentTree } from '$lib/viewmodels/document-tree.svelte';
	import { colorFor, createEditor, type EditorVM } from '$lib/viewmodels/editor.svelte';
	import { session } from '$lib/viewmodels/session.svelte';
	import { createSharing, type SharingVM } from '$lib/viewmodels/sharing.svelte';
	import { dialogs } from '$lib/viewmodels/dialogs.svelte';
	import { toasts } from '$lib/viewmodels/toasts.svelte';
	import { saveTemplate } from '$lib/api/templates';

	registerBuiltinBlocks();

	const documentId = $derived(page.params.documentId!);
	const workspaceId = $derived(page.params.workspaceId!);

	let doc = $state<Document | null>(null);
	let crumbs = $state<PathCrumb[]>([]);

	// The last crumb (the current document) reflects the live title, so a rename
	// updates the breadcrumb without a reload. When the path failed to load, fall
	// back to a single crumb carrying just the title.
	const displayCrumbs = $derived.by<PathCrumb[]>(() => {
		if (crumbs.length === 0) {
			return doc ? [{ kind: 'document', id: doc.id, label: doc.title }] : [];
		}
		const last = crumbs.length - 1;
		return crumbs.map((crumb, index) =>
			index === last && doc ? { ...crumb, label: doc.title } : crumb
		);
	});

	async function saveAsTemplate() {
		const name = await dialogs.prompt({
			title: 'Save as template',
			message: 'Name this template — new documents can be created from it.',
			placeholder: 'e.g. Meeting notes',
			initial: doc?.title && doc.title !== 'Untitled' ? doc.title : '',
			confirmLabel: 'Save'
		});
		if (name === null) return;
		try {
			await saveTemplate(workspaceId, name.trim() || 'Untitled template', documentId);
			toasts.success('Saved as template');
		} catch {
			toasts.error("Couldn't save the template");
		}
	}
	let titleDraft = $state('');
	let editor = $state<EditorVM | null>(null);
	let agent = $state<AgentPanelVM | null>(null);
	let agentOpen = $state(false);
	let sharing = $state<SharingVM | null>(null);
	let shareOpen = $state(false);
	let exportOpen = $state(false);

	let connectors = $state<ConnectorsVM | null>(null);

	$effect(() => {
		agent = createAgentPanel(documentId, {
			// Insert applies to the live editor doc (CRDT peer): immediate and
			// offline-safe, rather than a server round-trip the offline tab can't see.
			insertLocal: (blocks) => editor?.insertBlocks(blocks as never)
		});
		const sharingVm = createSharing(workspaceId, documentId);
		sharing = sharingVm;
		sharingVm.load();
		const connectorsVm = createConnectors(workspaceId);
		connectors = connectorsVm;
		connectorsVm.load();
	});

	// Depends only on documentId — never on `editor`, which it writes
	// (reading it here would loop the effect through create/destroy).
	$effect(() => {
		const id = documentId;
		let instance: EditorVM | null = null;
		let cancelled = false;
		doc = null;
		crumbs = [];

		// Load the breadcrumb path in parallel; a failure leaves crumbs empty and
		// the header falls back to just the title.
		getDocumentPath(id)
			.then((path) => {
				if (!cancelled) crumbs = path;
			})
			.catch(() => {});

		getDocument(id).then((loaded) => {
			if (cancelled) return;
			doc = loaded;
			titleDraft = loaded.title === 'Untitled' ? '' : loaded.title;
			if (session.getAccessToken()) {
				// Pass the session itself, not a token snapshot: the WS reconnects
				// long after a 15-minute access token has expired.
				instance = createEditor(id, session, session.userId ?? 'me');
				editor = instance;
			}
		});

		return () => {
			cancelled = true;
			instance?.destroy();
			editor = null;
		};
	});

	async function commitTitle() {
		if (!doc) return;
		const next = titleDraft.trim() || 'Untitled';
		if (next !== doc.title) {
			await documentTree.rename(doc.id, next);
			doc = { ...doc, title: next };
		}
	}

	const statusLabel = $derived(
		editor?.status === 'connected'
			? 'Synced'
			: editor?.status === 'connecting'
				? 'Connecting…'
				: 'Offline — will sync'
	);
</script>

{#if doc}
	<div class="split">
	<article class="doc">
		<header class="topbar">
			<Breadcrumb crumbs={displayCrumbs} {workspaceId} onNavigate={(path) => goto(path)} />
			<div class="right">
				{#if editor && editor.peers.length > 0}
					<div class="presence" data-testid="presence">
						{#each editor.peers.slice(0, 4) as peer (peer.user_id)}
							<span class="avatar" style:background={colorFor(peer.user_id)}>
								{peer.user_id.slice(0, 2).toUpperCase()}
							</span>
						{/each}
					</div>
				{/if}
				<span
					class="chip"
					class:chip-accent={editor?.status === 'connected'}
					data-testid="sync-status">{statusLabel}</span
				>
				<button
					class="btn btn-secondary export"
					data-testid="save-template"
					title="Save this document as a reusable template"
					onclick={saveAsTemplate}>Save as template</button
				>
				<button
					class="btn btn-secondary export"
					data-testid="open-history"
					title="Version history"
					onclick={() => historyModal.open()}>History</button
				>
				<button
					class="btn btn-secondary export"
					data-testid="export-open"
					title="Export document"
					onclick={() => (exportOpen = true)}>Export</button
				>
				<button
					class="btn btn-primary share"
					data-testid="share-open"
					onclick={() => (shareOpen = true)}>Share</button
				>
				<button
					class="agent-toggle"
					class:open={agentOpen}
					title="Agent"
					data-testid="agent-toggle"
					onclick={() => (agentOpen = !agentOpen)}>✦</button
				>
			</div>
		</header>

		<div class="canvas">
			<input
				class="title"
				placeholder="Untitled"
				bind:value={titleDraft}
				onblur={commitTitle}
				onkeydown={(event) => event.key === 'Enter' && (event.target as HTMLInputElement).blur()}
				data-testid="doc-title"
			/>
			{#if editor}
				<BlockEditor {editor} {sharing} />
			{/if}
			<BacklinksPanel documentId={doc.id} />
		</div>
	</article>
	{#if agentOpen && agent}
		<AgentPanel
			{agent}
			{connectors}
			{workspaceId}
			focusedBlockId={editor?.focusedId ?? null}
			onclose={() => (agentOpen = false)}
		/>
	{/if}
	{#if shareOpen && sharing}
		<ShareDialog {sharing} onclose={() => (shareOpen = false)} />
	{/if}
	{#if exportOpen}
		<ExportDialog
			title={doc.title}
			blocks={editor?.blocks ?? []}
			onclose={() => (exportOpen = false)}
		/>
	{/if}
	{#if historyModal.isOpen}
		<HistoryModal documentId={doc.id} />
	{/if}
	</div>
{:else}
	<div class="loading">Loading…</div>
{/if}

<style>
	.split {
		display: flex;
		height: 100%;
	}
	.doc {
		flex: 1;
		display: flex;
		flex-direction: column;
		min-height: 100%;
		min-width: 0;
		overflow-y: auto;
	}
	.share {
		padding: 4px 12px;
		font-size: 12px;
	}
	.export {
		padding: 4px 12px;
		font-size: 12px;
	}
	.agent-toggle {
		padding: 3px 9px;
		border-radius: var(--r-control);
		color: var(--ai);
		font-size: 14px;
	}
	.agent-toggle:hover,
	.agent-toggle.open {
		background: var(--aibg);
	}
	.topbar {
		position: sticky;
		top: 0;
		z-index: 10;
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 10px 20px;
		background: var(--bg1);
		border-bottom: 1px solid var(--line);
	}
	.right {
		display: flex;
		align-items: center;
		gap: 10px;
	}
	.presence {
		display: flex;
	}
	.avatar {
		display: grid;
		place-items: center;
		width: 22px;
		height: 22px;
		border-radius: 50%;
		color: #fff;
		font-size: 9px;
		font-weight: 600;
		border: 2px solid var(--bg1);
		margin-left: -6px;
	}
	.canvas {
		width: min(760px, 92%);
		margin: 0 auto;
		padding: 48px 0 120px;
	}
	.title {
		width: 100%;
		border: none;
		outline: none;
		background: transparent;
		font-family: var(--font-ui);
		font-size: 34px;
		font-weight: 700;
		color: var(--tx);
		padding: 0;
		margin-bottom: 18px;
	}
	.title::placeholder {
		color: var(--tx3);
	}
	.loading {
		display: grid;
		place-items: center;
		height: 100%;
		color: var(--tx3);
	}
</style>
