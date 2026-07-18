<script lang="ts">
	import type { PropertyDef } from '$lib/api/collections';
	import { TITLE_PROPERTY, type CollectionVM } from '$lib/viewmodels/collection.svelte';
	import { operatorsForType } from '$lib/viewmodels/collection.svelte';
	import FilterRule from './FilterRule.svelte';

	let { vm }: { vm: CollectionVM } = $props();

	let open = $state(false);

	// Pickable properties: the schema plus the synthetic Title property, so a
	// member can filter on the document title.
	const pickable = $derived<PropertyDef[]>([
		{ id: TITLE_PROPERTY, name: 'Name', type: 'text', options: [] },
		...vm.properties
	]);

	function addFilter() {
		const first = pickable[0];
		const op = operatorsForType(first.type)[0].value;
		vm.addFilter(first.id, op, null);
	}
</script>

<svelte:window onkeydown={(e) => e.key === 'Escape' && (open = false)} />

<div class="wrap">
	<button
		class="toolbar-btn"
		class:active={vm.activeFilterCount > 0}
		aria-haspopup="menu"
		aria-expanded={open}
		data-testid="filter-button"
		onclick={() => (open = !open)}
	>
		Filter{#if vm.activeFilterCount > 0}<span class="count" data-testid="filter-count"
				>{vm.activeFilterCount}</span
			>{/if}
	</button>

	{#if open}
		<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
		<div class="scrim" onclick={() => (open = false)}></div>
		<div class="panel" role="menu" data-testid="filter-panel">
			{#if vm.filters.length === 0}
				<p class="empty">No filters yet.</p>
			{:else}
				<div class="rules">
					{#each vm.filters as filter, i (i)}
						<FilterRule
							{filter}
							properties={pickable}
							onchange={(patch) => vm.updateFilter(i, patch)}
							onremove={() => vm.removeFilter(i)}
						/>
					{/each}
				</div>
			{/if}
			<button class="add" data-testid="add-filter" onclick={addFilter}>＋ Add filter</button>
		</div>
	{/if}
</div>

<style>
	.wrap {
		position: relative;
	}
	.toolbar-btn {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		padding: 5px 10px;
		border: 1px solid var(--line);
		border-radius: var(--r-control);
		background: var(--bg0);
		color: var(--tx2);
		font-size: 13px;
	}
	.toolbar-btn:hover {
		color: var(--tx);
	}
	.toolbar-btn.active {
		color: var(--acc-strong);
		border-color: var(--acc);
	}
	.count {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-width: 16px;
		height: 16px;
		padding: 0 4px;
		border-radius: 8px;
		background: var(--accbg);
		color: var(--acc-strong);
		font-size: 11px;
		font-weight: 600;
	}
	.scrim {
		position: fixed;
		inset: 0;
		z-index: 1200;
	}
	.panel {
		position: absolute;
		z-index: 1201;
		top: calc(100% + 4px);
		left: 0;
		min-width: 320px;
		padding: 10px;
		background: var(--bg1, #fff);
		border: 1px solid var(--line);
		border-radius: 10px;
		box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
		display: flex;
		flex-direction: column;
		gap: 8px;
	}
	.rules {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}
	.empty {
		margin: 0;
		color: var(--tx3);
		font-size: 13px;
	}
	.add {
		align-self: flex-start;
		padding: 4px 8px;
		color: var(--acc-strong);
		font-size: 13px;
		font-weight: 500;
		border-radius: var(--r-control);
	}
	.add:hover {
		background: var(--accbg);
	}
</style>
