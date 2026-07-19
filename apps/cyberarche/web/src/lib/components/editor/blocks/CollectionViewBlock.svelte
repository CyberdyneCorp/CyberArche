<script lang="ts">
	/** Embedded collection block (collections-inline-embed spec): the inline
	 * database is a real collection rendered inside a document. It stores only
	 * `{ collection_id, view_id }` and reuses the full-page collection VM +
	 * `CollectionTable`, so it inherits formulas, relations, rollups, reminders,
	 * bulk actions and all four views for free.
	 *
	 * When first inserted the block owns no collection yet; it self-initialises
	 * once by creating an empty collection and persisting its ids into the block. */
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { createCollection as apiCreateCollection } from '$lib/api/collections';
	import CollectionTable from '$lib/components/CollectionTable.svelte';
	import type { BlockComponentProps } from '$lib/editor/registry';
	import { createCollection as createCollectionVM, type CollectionVM } from '$lib/viewmodels/collection.svelte';
	import type { EditorVM } from '$lib/viewmodels/editor.svelte';

	let { block, editor }: BlockComponentProps = $props();
	const vmEditor = editor as EditorVM;

	const workspaceId = $derived(page.params.workspaceId!);
	const ro = $derived(vmEditor.readOnly);
	const collectionId = $derived((block.data.collection_id as string) ?? '');

	let vm = $state<CollectionVM | null>(null);
	let loadedId: string | null = null;
	// Guards the one-shot self-initialisation against re-render double-creates.
	let initializing = false;

	/** Create the backing collection exactly once, then persist its ids. */
	async function initCollection(): Promise<void> {
		if (initializing || block.data.collection_id) return;
		initializing = true;
		const created = await apiCreateCollection(workspaceId, '');
		vmEditor.updateData(block.id, {
			collection_id: created.id,
			view_id: created.views[0].id
		});
	}

	/** Build + load the collection VM the first time an id is available. */
	function ensureLoaded(id: string): void {
		if (loadedId === id) return;
		loadedId = id;
		const instance = createCollectionVM(id);
		vm = instance;
		void instance.load();
	}

	$effect(() => {
		if (collectionId) ensureLoaded(collectionId);
		else if (!ro) void initCollection();
	});

	function openRow(rowId: string): void {
		void goto(`/w/${workspaceId}/d/${rowId}`);
	}
</script>

{#if vm}
	<div class="embed" data-testid="collection-view-block">
		{#if vm.busy && !vm.collection}
			<p class="placeholder">Loading…</p>
		{:else}
			<CollectionTable {vm} onOpenRow={openRow} readOnly={ro} />
		{/if}
	</div>
{:else if ro}
	<p class="placeholder" data-testid="collection-empty">Empty database</p>
{:else}
	<p class="placeholder" data-testid="collection-initialising">Creating database…</p>
{/if}

<style>
	.embed {
		background: var(--bg2);
		border: 1px solid var(--line);
		border-radius: var(--r-block);
		/* Stay within the document flow: cap the height and scroll a tall table
		   rather than assuming the full viewport. */
		max-height: 560px;
		overflow: auto;
	}
	.placeholder {
		padding: 20px;
		color: var(--tx3);
		font-size: 13px;
	}
</style>
