<script lang="ts">
	import type { CollectionVM } from '$lib/viewmodels/collection.svelte';
	import CollectionCard from './CollectionCard.svelte';

	let {
		vm,
		onOpenRow
	}: {
		vm: CollectionVM;
		onOpenRow: (rowId: string) => void;
	} = $props();
</script>

{#if vm.rows.length === 0}
	<p class="empty" data-testid="gallery-empty">No rows yet</p>
{:else}
	<div class="gallery" data-testid="collection-gallery">
		{#each vm.rows as row (row.id)}
			<CollectionCard {row} properties={vm.properties} {onOpenRow} />
		{/each}
	</div>
{/if}

<style>
	.gallery {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
		gap: 12px;
	}
	.empty {
		margin: 24px 0;
		padding: 16px;
		text-align: center;
		color: var(--tx3);
		font-size: 14px;
	}
</style>
