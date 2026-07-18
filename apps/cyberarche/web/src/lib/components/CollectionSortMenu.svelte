<script lang="ts">
	import type { PropertyDef } from '$lib/api/collections';
	import { TITLE_PROPERTY, type CollectionVM } from '$lib/viewmodels/collection.svelte';

	let { vm }: { vm: CollectionVM } = $props();

	let open = $state(false);

	const pickable = $derived<PropertyDef[]>([
		{ id: TITLE_PROPERTY, name: 'Name', type: 'text', options: [] },
		...vm.properties
	]);

	function addSort() {
		vm.addSort(pickable[0].id, 'asc');
	}
</script>

<svelte:window onkeydown={(e) => e.key === 'Escape' && (open = false)} />

<div class="wrap">
	<button
		class="toolbar-btn"
		class:active={vm.activeSortCount > 0}
		aria-haspopup="menu"
		aria-expanded={open}
		data-testid="sort-button"
		onclick={() => (open = !open)}
	>
		Sort{#if vm.activeSortCount > 0}<span class="count" data-testid="sort-count"
				>{vm.activeSortCount}</span
			>{/if}
	</button>

	{#if open}
		<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
		<div class="scrim" onclick={() => (open = false)}></div>
		<div class="panel" role="menu" data-testid="sort-panel">
			{#if vm.sorts.length === 0}
				<p class="empty">No sorts yet.</p>
			{:else}
				<div class="rules">
					{#each vm.sorts as sort, i (i)}
						<div class="rule" data-testid="sort-rule">
							<select
								class="control"
								value={sort.property_id}
								data-testid="sort-property"
								onchange={(e) => vm.updateSort(i, { property_id: e.currentTarget.value })}
							>
								{#each pickable as prop (prop.id)}
									<option value={prop.id}>{prop.name}</option>
								{/each}
							</select>
							<select
								class="control dir"
								value={sort.direction}
								data-testid="sort-direction"
								onchange={(e) =>
									vm.updateSort(i, { direction: e.currentTarget.value as 'asc' | 'desc' })}
							>
								<option value="asc">Ascending</option>
								<option value="desc">Descending</option>
							</select>
							<button
								class="icon"
								data-testid="sort-up"
								title="Move up"
								disabled={i === 0}
								onclick={() => vm.moveSort(i, 'up')}>↑</button
							>
							<button
								class="icon"
								data-testid="sort-down"
								title="Move down"
								disabled={i === vm.sorts.length - 1}
								onclick={() => vm.moveSort(i, 'down')}>↓</button
							>
							<button
								class="icon remove"
								data-testid="sort-remove"
								title="Remove sort"
								onclick={() => vm.removeSort(i)}>×</button
							>
						</div>
					{/each}
				</div>
			{/if}
			<button class="add" data-testid="add-sort" onclick={addSort}>＋ Add sort</button>
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
	.rule {
		display: flex;
		align-items: center;
		gap: 6px;
	}
	.control {
		padding: 4px 6px;
		border: 1px solid var(--line);
		border-radius: var(--r-control);
		background: var(--bg0);
		color: var(--tx);
		font-size: 13px;
		min-width: 0;
		flex: 1;
	}
	.control.dir {
		flex: 0 0 auto;
	}
	.icon {
		color: var(--tx3);
		font-size: 14px;
		line-height: 1;
		padding: 2px 5px;
		flex: 0 0 auto;
	}
	.icon:hover:not(:disabled) {
		color: var(--tx);
	}
	.icon:disabled {
		opacity: 0.3;
		cursor: default;
	}
	.icon.remove:hover:not(:disabled) {
		color: var(--rose);
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
