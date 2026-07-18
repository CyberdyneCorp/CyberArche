<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import CollectionTable from '$lib/components/CollectionTable.svelte';
	import { createCollection, type CollectionVM } from '$lib/viewmodels/collection.svelte';

	const collectionId = $derived(page.params.collectionId!);
	const workspaceId = $derived(page.params.workspaceId!);

	let vm = $state<CollectionVM | null>(null);

	$effect(() => {
		const id = collectionId;
		const instance = createCollection(id);
		vm = instance;
		instance.load();
	});

	function openRow(rowId: string) {
		goto(`/w/${workspaceId}/d/${rowId}`);
	}
</script>

{#if vm}
	<main class="page">
		{#if vm.busy && !vm.collection}
			<p class="loading">Loading…</p>
		{:else}
			<CollectionTable {vm} onOpenRow={openRow} />
		{/if}
	</main>
{/if}

<style>
	.page {
		flex: 1;
		min-width: 0;
		overflow-y: auto;
	}
	.loading {
		padding: 40px;
		color: var(--tx3);
	}
</style>
