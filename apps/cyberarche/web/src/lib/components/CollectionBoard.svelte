<script lang="ts">
	import { groupRows, type CollectionVM } from '$lib/viewmodels/collection.svelte';
	import CollectionCard from './CollectionCard.svelte';

	let {
		vm,
		onOpenRow
	}: {
		vm: CollectionVM;
		onOpenRow: (rowId: string) => void;
	} = $props();

	const groupBy = $derived(vm.groupByProperty);
	const groups = $derived(groupRows(vm.rows, groupBy));
	// Card fields exclude the grouping property (it's implied by the column).
	const cardProps = $derived(vm.properties.filter((p) => p.id !== groupBy?.id));
</script>

{#if !groupBy}
	<div class="prompt" data-testid="board-groupby-prompt">
		{#if vm.selectProperties.length > 0}
			<label class="prompt-label">
				Group by
				<select
					class="control"
					data-testid="board-groupby-select"
					onchange={(e) => vm.setBoardGroupBy(e.currentTarget.value || null)}
				>
					<option value="">Choose a property…</option>
					{#each vm.selectProperties as property (property.id)}
						<option value={property.id}>{property.name}</option>
					{/each}
				</select>
			</label>
		{:else}
			<p class="hint">Add a single-select property to group this board.</p>
		{/if}
	</div>
{:else}
	<div class="board" data-testid="collection-board">
		<div class="board-bar">
			<label class="prompt-label">
				Group by
				<select
					class="control"
					data-testid="board-groupby-select"
					value={groupBy.id}
					onchange={(e) => vm.setBoardGroupBy(e.currentTarget.value || null)}
				>
					{#each vm.selectProperties as property (property.id)}
						<option value={property.id}>{property.name}</option>
					{/each}
				</select>
			</label>
		</div>
		<div class="columns">
			{#each groups as group (group.key ?? '__uncategorized__')}
				<section class="column" data-testid="board-column">
					<header class="col-head">
						<span class="col-label">{group.label}</span>
						<span class="col-count" data-testid="board-column-count">{group.rows.length}</span>
					</header>
					<div class="col-body">
						{#each group.rows as row (row.id)}
							<div class="card-wrap" data-testid="board-card">
								<CollectionCard {row} properties={cardProps} {onOpenRow} />
								<label class="move">
									<span class="visually-hidden">Move {row.title} to column</span>
									<select
										class="control move-select"
										data-testid="board-card-move"
										value={group.key ?? ''}
										onchange={(e) =>
											vm.setRowGroup(row.id, groupBy.id, e.currentTarget.value || null)}
									>
										{#each groupBy.options as option (option)}
											<option value={option}>{option}</option>
										{/each}
										<option value="">Uncategorized</option>
									</select>
								</label>
							</div>
						{/each}
						{#if group.rows.length === 0}
							<p class="col-empty" data-testid="board-column-empty">No cards</p>
						{/if}
					</div>
				</section>
			{/each}
		</div>
	</div>
{/if}

<style>
	.prompt {
		padding: 20px 0;
	}
	.prompt-label {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		font-size: 13px;
		color: var(--tx2);
	}
	.hint {
		margin: 0;
		color: var(--tx3);
		font-size: 13px;
	}
	.board {
		display: flex;
		flex-direction: column;
		gap: 12px;
	}
	.board-bar {
		display: flex;
		align-items: center;
		gap: 8px;
	}
	.control {
		padding: 4px 6px;
		border: 1px solid var(--line);
		border-radius: var(--r-control);
		background: var(--bg0);
		color: var(--tx);
		font-size: 13px;
	}
	.columns {
		display: flex;
		gap: 12px;
		overflow-x: auto;
		padding-bottom: 8px;
		align-items: flex-start;
	}
	.column {
		flex: 0 0 260px;
		display: flex;
		flex-direction: column;
		gap: 8px;
		background: var(--bg0);
		border: 1px solid var(--line);
		border-radius: 10px;
		padding: 10px;
		max-height: 100%;
	}
	.col-head {
		display: flex;
		align-items: center;
		gap: 6px;
	}
	.col-label {
		font-weight: 600;
		font-size: 13px;
		color: var(--tx);
	}
	.col-count {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-width: 18px;
		height: 18px;
		padding: 0 5px;
		border-radius: 9px;
		background: var(--accbg);
		color: var(--acc-strong);
		font-size: 11px;
		font-weight: 600;
	}
	.col-body {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}
	.card-wrap {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}
	.move-select {
		width: 100%;
		font-size: 12px;
		color: var(--tx3);
	}
	.col-empty {
		margin: 0;
		padding: 12px;
		text-align: center;
		color: var(--tx3);
		font-size: 12px;
	}
	.visually-hidden {
		position: absolute;
		width: 1px;
		height: 1px;
		padding: 0;
		margin: -1px;
		overflow: hidden;
		clip: rect(0, 0, 0, 0);
		white-space: nowrap;
		border: 0;
	}
</style>
