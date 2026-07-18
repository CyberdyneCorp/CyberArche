<script lang="ts">
	import type { PropertyType } from '$lib/api/collections';
	import type { CollectionVM } from '$lib/viewmodels/collection.svelte';
	import CollectionCell from './CollectionCell.svelte';
	import CollectionFilterMenu from './CollectionFilterMenu.svelte';
	import CollectionSortMenu from './CollectionSortMenu.svelte';

	let {
		vm,
		onOpenRow
	}: {
		vm: CollectionVM;
		/** Open a row as a full document page. */
		onOpenRow: (rowId: string) => void;
	} = $props();

	// --- editable collection name ---
	let nameDraft = $state('');
	let editingName = $state(false);

	function startRename() {
		nameDraft = vm.collection?.name ?? '';
		editingName = true;
	}
	function commitRename() {
		editingName = false;
		const next = nameDraft.trim();
		if (next && next !== vm.collection?.name) vm.rename(next);
	}

	// --- add property mini-form ---
	const TYPES: PropertyType[] = ['text', 'number', 'select', 'multi_select', 'date', 'checkbox', 'url'];
	let addingProperty = $state(false);
	let propName = $state('');
	let propType = $state<PropertyType>('text');
	let propOptions = $state('');

	function hasOptions(type: PropertyType): boolean {
		return type === 'select' || type === 'multi_select';
	}

	async function submitProperty() {
		const name = propName.trim();
		if (!name) return;
		const options = hasOptions(propType)
			? propOptions.split(',').map((o) => o.trim()).filter(Boolean)
			: [];
		await vm.addProperty(name, propType, options);
		propName = '';
		propOptions = '';
		propType = 'text';
		addingProperty = false;
	}
</script>

<section class="collection">
	<header class="head">
		{#if editingName}
			<!-- svelte-ignore a11y_autofocus -->
			<input
				class="name-input"
				bind:value={nameDraft}
				autofocus
				data-testid="collection-name-input"
				onblur={commitRename}
				onkeydown={(e) => e.key === 'Enter' && commitRename()}
			/>
		{:else}
			<button class="name" data-testid="collection-name" onclick={startRename}>
				{vm.collection?.name ?? 'Collection'}
			</button>
		{/if}
	</header>

	<!-- View tabs. A clean seam for later PRs: more view kinds render their own
	     surface; only the table view is built today. -->
	<nav class="view-tabs" data-testid="view-tabs">
		{#each vm.collection?.views ?? [] as view (view.id)}
			<button
				class="view-tab"
				class:active={vm.currentView?.id === view.id}
				data-testid="view-tab"
				onclick={() => vm.selectView(view.id)}
			>
				{view.name}
			</button>
		{/each}
	</nav>

	{#if vm.currentView && vm.currentView.kind !== 'table'}
		<p class="placeholder">The {vm.currentView.kind} view is coming soon.</p>
	{:else}
		<div class="toolbar" data-testid="collection-toolbar">
			<CollectionFilterMenu {vm} />
			<CollectionSortMenu {vm} />
		</div>
		<div class="table-wrap">
			<table class="table" data-testid="collection-table">
				<thead>
					<tr>
						<th class="title-col">Name</th>
						{#each vm.properties as property (property.id)}
							<th data-testid="column-header">{property.name}</th>
						{/each}
						<th class="add-col">
							<button
								class="add-prop"
								data-testid="add-property"
								title="Add property"
								onclick={() => (addingProperty = !addingProperty)}>＋</button
							>
						</th>
					</tr>
				</thead>
				<tbody>
					{#each vm.rows as row (row.id)}
						<tr data-testid="collection-row">
							<td class="title-col">
								<div class="title-cell">
									<button
										class="open-row"
										title="Open as page"
										data-testid="open-row"
										onclick={() => onOpenRow(row.id)}>⤢</button
									>
									<input
										class="cell-input title-input"
										value={row.title}
										data-testid="row-title"
										onchange={(e) => vm.renameRow(row.id, e.currentTarget.value)}
									/>
								</div>
							</td>
							{#each vm.properties as property (property.id)}
								<td>
									<CollectionCell
										{property}
										value={row.properties[property.id]}
										onchange={(value) => vm.setCell(row.id, property.id, value)}
									/>
								</td>
							{/each}
							<td></td>
						</tr>
					{/each}
				</tbody>
			</table>

			{#if vm.rows.length === 0 && vm.activeFilterCount > 0}
				<p class="empty-rows" data-testid="no-rows">No rows match the current filters</p>
			{/if}

			<button class="add-row" data-testid="add-row" onclick={() => vm.addRow()}>
				＋ Add row
			</button>
		</div>
	{/if}

	{#if addingProperty}
		<form class="prop-form" data-testid="add-property-form" onsubmit={(e) => { e.preventDefault(); submitProperty(); }}>
			<input
				class="input"
				placeholder="Property name"
				bind:value={propName}
				data-testid="prop-name"
			/>
			<select class="input" bind:value={propType} data-testid="prop-type">
				{#each TYPES as type (type)}
					<option value={type}>{type}</option>
				{/each}
			</select>
			{#if hasOptions(propType)}
				<input
					class="input"
					placeholder="Options (comma-separated)"
					bind:value={propOptions}
					data-testid="prop-options"
				/>
			{/if}
			<button type="submit" class="btn" data-testid="prop-submit">Add</button>
		</form>
	{/if}

	{#if vm.error}
		<p class="error" data-testid="collection-error">{vm.error}</p>
	{/if}
</section>

<style>
	.collection {
		padding: 24px 32px;
		max-width: 100%;
	}
	.head {
		margin-bottom: 12px;
	}
	.name,
	.name-input {
		font-size: 26px;
		font-weight: 700;
		color: var(--tx);
		background: transparent;
		border: none;
		padding: 2px 4px;
		text-align: left;
	}
	.name-input:focus {
		outline: 1px solid var(--acc);
		border-radius: 4px;
	}
	.view-tabs {
		display: flex;
		gap: 4px;
		border-bottom: 1px solid var(--line);
		margin-bottom: 12px;
	}
	.view-tab {
		padding: 6px 10px;
		color: var(--tx2);
		border-bottom: 2px solid transparent;
	}
	.view-tab.active {
		color: var(--tx);
		border-bottom-color: var(--acc);
		font-weight: 500;
	}
	.toolbar {
		display: flex;
		gap: 8px;
		margin-bottom: 10px;
	}
	.table-wrap {
		overflow-x: auto;
	}
	.empty-rows {
		margin: 12px 0;
		padding: 16px;
		color: var(--tx3);
		text-align: center;
		font-size: 14px;
	}
	.table {
		border-collapse: collapse;
		width: 100%;
	}
	.table th,
	.table td {
		border: 1px solid var(--line);
		padding: 4px 8px;
		text-align: left;
		vertical-align: middle;
		min-width: 120px;
	}
	.table th {
		font-size: 12px;
		font-weight: 600;
		color: var(--tx2);
		background: var(--bg0);
	}
	.title-col {
		min-width: 220px;
	}
	.title-cell {
		display: flex;
		align-items: center;
		gap: 6px;
	}
	.title-input {
		flex: 1;
		font-weight: 500;
	}
	.cell-input {
		width: 100%;
		border: none;
		background: transparent;
		color: var(--tx);
		font: inherit;
		padding: 2px 4px;
	}
	.cell-input:focus {
		outline: 1px solid var(--acc);
		border-radius: 4px;
	}
	.open-row {
		color: var(--tx3);
		font-size: 13px;
	}
	.open-row:hover {
		color: var(--acc-strong);
	}
	.add-col {
		min-width: 40px;
		width: 40px;
	}
	.add-prop {
		color: var(--tx3);
	}
	.add-prop:hover {
		color: var(--tx);
	}
	.add-row {
		margin-top: 8px;
		padding: 6px 10px;
		color: var(--acc-strong);
		font-weight: 500;
		border-radius: var(--r-control);
	}
	.add-row:hover {
		background: var(--accbg);
	}
	.prop-form {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
		margin-top: 12px;
		align-items: center;
	}
	.input {
		padding: 5px 8px;
		border: 1px solid var(--line);
		border-radius: var(--r-control);
		background: var(--bg0);
		color: var(--tx);
	}
	.btn {
		padding: 5px 12px;
		border-radius: var(--r-control);
		background: var(--acc);
		color: #fff;
		font-weight: 500;
	}
	.placeholder {
		color: var(--tx3);
		padding: 24px 0;
	}
	.error {
		margin-top: 10px;
		color: var(--rose);
	}
</style>
