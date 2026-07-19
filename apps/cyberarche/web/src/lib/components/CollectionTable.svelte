<script lang="ts">
	import type { Collection, PropertyDef, PropertyType, ViewKind } from '$lib/api/collections';
	import type { CollectionVM } from '$lib/viewmodels/collection.svelte';
	import { TITLE_PROPERTY } from '$lib/viewmodels/collection.svelte';
	import CollectionBoard from './CollectionBoard.svelte';
	import CollectionBulkBar from './CollectionBulkBar.svelte';
	import CollectionCalendar from './CollectionCalendar.svelte';
	import CollectionCell from './CollectionCell.svelte';
	import CollectionFilterMenu from './CollectionFilterMenu.svelte';
	import CollectionGallery from './CollectionGallery.svelte';
	import CollectionSortMenu from './CollectionSortMenu.svelte';

	let {
		vm,
		onOpenRow
	}: {
		vm: CollectionVM;
		/** Open a row as a full document page. */
		onOpenRow: (rowId: string) => void;
	} = $props();

	// --- add view mini-form ---
	const VIEW_KINDS: ViewKind[] = ['table', 'board', 'gallery', 'calendar'];
	let addingView = $state(false);
	let viewName = $state('');
	let viewKind = $state<ViewKind>('board');

	async function submitView() {
		const name = viewName.trim();
		if (!name) return;
		await vm.createViewOfKind(name, viewKind);
		viewName = '';
		viewKind = 'board';
		addingView = false;
	}

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
	const TYPES: PropertyType[] = [
		'text',
		'number',
		'select',
		'multi_select',
		'date',
		'checkbox',
		'url',
		'formula',
		'relation',
		'rollup'
	];
	const ROLLUP_FUNCTIONS = [
		'count',
		'sum',
		'average',
		'min',
		'max',
		'earliest',
		'latest',
		'list'
	];
	// Reminder lead times for a date property, in minutes (-1 = no reminder).
	const REMINDER_OPTIONS: { label: string; value: number }[] = [
		{ label: 'No reminder', value: -1 },
		{ label: 'At the time', value: 0 },
		{ label: '5 minutes before', value: 5 },
		{ label: '1 hour before', value: 60 },
		{ label: '1 day before', value: 1440 },
		{ label: '1 week before', value: 10080 }
	];
	let addingProperty = $state(false);
	let propName = $state('');
	let propType = $state<PropertyType>('text');
	let propOptions = $state('');
	let propFormula = $state('');
	let propReminder = $state(-1);
	// Relation config.
	let relTarget = $state('');
	let workspaceCollections = $state<Collection[]>([]);
	// Rollup config.
	let rollupRelPropId = $state('');
	let rollupTargetPropId = $state(TITLE_PROPERTY);
	let rollupFn = $state('count');
	let rollupTargetOptions = $state<PropertyDef[]>([]);

	function hasOptions(type: PropertyType): boolean {
		return type === 'select' || type === 'multi_select';
	}

	// --- bulk row selection (Table view only) ---
	const rowIds = $derived(vm.rows.map((r) => r.id));
	const allSelected = $derived(rowIds.length > 0 && rowIds.every((id) => vm.isSelected(id)));
	const someSelected = $derived(rowIds.some((id) => vm.isSelected(id)));

	/** Load the collections a relation may target (once the picker is shown). */
	async function loadTargets() {
		if (workspaceCollections.length === 0) {
			workspaceCollections = await vm.loadWorkspaceCollections();
		}
	}

	/** When the rollup source relation changes, fetch the target collection's
	 * properties so the target-property picker can list them. */
	async function onRollupSourceChange(relationPropertyId: string) {
		rollupRelPropId = relationPropertyId;
		rollupTargetPropId = TITLE_PROPERTY;
		const source = vm.relationProperties.find((p) => p.id === relationPropertyId);
		rollupTargetOptions = source?.relation_collection_id
			? await vm.loadCollectionProperties(source.relation_collection_id)
			: [];
	}

	async function openAddProperty() {
		addingProperty = !addingProperty;
		if (addingProperty) await loadTargets();
	}

	function relationRollupConfig() {
		if (propType === 'relation') return { relation_collection_id: relTarget };
		if (propType === 'rollup')
			return {
				rollup_relation_property_id: rollupRelPropId,
				rollup_target_property_id: rollupTargetPropId,
				rollup_function: rollupFn
			};
		return {};
	}

	async function submitProperty() {
		const name = propName.trim();
		if (!name) return;
		const options = hasOptions(propType)
			? propOptions.split(',').map((o) => o.trim()).filter(Boolean)
			: [];
		const formula = propType === 'formula' ? propFormula.trim() : '';
		const reminder = propType === 'date' ? propReminder : -1;
		await vm.addProperty(name, propType, options, formula, relationRollupConfig(), reminder);
		propName = '';
		propOptions = '';
		propFormula = '';
		propType = 'text';
		relTarget = '';
		rollupRelPropId = '';
		rollupTargetPropId = TITLE_PROPERTY;
		rollupFn = 'count';
		propReminder = -1;
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

	<!-- View tabs. Each view kind renders its own surface below; the "+" adds a
	     new view of a chosen kind. -->
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
		<button
			class="add-view"
			data-testid="add-view"
			title="Add view"
			onclick={() => (addingView = !addingView)}>＋</button
		>
	</nav>

	{#if addingView}
		<form
			class="prop-form"
			data-testid="add-view-form"
			onsubmit={(e) => {
				e.preventDefault();
				submitView();
			}}
		>
			<input class="input" placeholder="View name" bind:value={viewName} data-testid="view-name" />
			<select class="input" bind:value={viewKind} data-testid="view-kind">
				{#each VIEW_KINDS as kind (kind)}
					<option value={kind}>{kind}</option>
				{/each}
			</select>
			<button type="submit" class="btn" data-testid="view-submit">Add</button>
		</form>
	{/if}

	<!-- Filters/sorts apply to every data view (the server returns already
	     filtered+sorted rows); the calendar placeholder omits the toolbar. -->
	{#if vm.currentView && vm.currentView.kind !== 'calendar'}
		<div class="toolbar" data-testid="collection-toolbar">
			<CollectionFilterMenu {vm} />
			<CollectionSortMenu {vm} />
		</div>
	{/if}

	{#if vm.currentView?.kind === 'board'}
		<CollectionBoard {vm} {onOpenRow} />
	{:else if vm.currentView?.kind === 'gallery'}
		<CollectionGallery {vm} {onOpenRow} />
	{:else if vm.currentView?.kind === 'calendar'}
		<CollectionCalendar {vm} {onOpenRow} />
	{:else}
		{#if vm.selectedCount > 0}
			<CollectionBulkBar {vm} />
		{/if}
		<div class="table-wrap">
			<table class="table" data-testid="collection-table">
				<thead>
					<tr>
						<th class="sel-col">
							<input
								type="checkbox"
								data-testid="select-all"
								checked={allSelected}
								indeterminate={someSelected && !allSelected}
								onchange={() => vm.toggleAll(rowIds)}
							/>
						</th>
						<th class="title-col">Name</th>
						{#each vm.properties as property (property.id)}
							<th data-testid="column-header"
								>{#if property.type === 'formula'}<span class="fx-marker" title="Formula">ƒ</span
									> {:else if property.type === 'relation'}<span class="fx-marker" title="Relation">🔗</span
										> {:else if property.type === 'rollup'}<span class="fx-marker" title="Rollup">Σ</span
										> {:else if property.type === 'date' && (property.reminder_minutes ?? -1) >= 0}<span
											class="fx-marker"
											title="Reminder">🔔</span
										> {/if}{property.name}</th
							>
						{/each}
						<th class="add-col">
							<button
								class="add-prop"
								data-testid="add-property"
								title="Add property"
								onclick={openAddProperty}>＋</button
							>
						</th>
					</tr>
				</thead>
				<tbody>
					{#each vm.rows as row (row.id)}
						<tr data-testid="collection-row" class:selected={vm.isSelected(row.id)}>
							<td class="sel-col">
								<input
									type="checkbox"
									data-testid="row-select"
									checked={vm.isSelected(row.id)}
									onchange={() => vm.toggleRow(row.id)}
								/>
							</td>
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
										relatedTitle={vm.relatedTitle}
										loadRelationOptions={property.type === 'relation' &&
										property.relation_collection_id
											? () => vm.loadRelationRows(property.relation_collection_id as string)
											: undefined}
										onchange={(value) =>
											property.type === 'relation'
												? vm.setRelation(row.id, property.id, value as string[])
												: vm.setCell(row.id, property.id, value)}
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
			{#if propType === 'formula'}
				<input
					class="input formula-input"
					placeholder={'Expression, e.g. prop("Price") * prop("Qty")'}
					bind:value={propFormula}
					data-testid="prop-formula"
				/>
			{/if}
			{#if propType === 'date'}
				<select class="input" bind:value={propReminder} data-testid="prop-reminder">
					{#each REMINDER_OPTIONS as opt (opt.value)}
						<option value={opt.value}>{opt.label}</option>
					{/each}
				</select>
			{/if}
			{#if propType === 'relation'}
				<select class="input" bind:value={relTarget} data-testid="prop-relation-target">
					<option value="">Target collection…</option>
					{#each workspaceCollections as target (target.id)}
						<option value={target.id}>{target.name}</option>
					{/each}
				</select>
			{/if}
			{#if propType === 'rollup'}
				<select
					class="input"
					data-testid="prop-rollup-relation"
					value={rollupRelPropId}
					onchange={(e) => onRollupSourceChange(e.currentTarget.value)}
				>
					<option value="">Relation…</option>
					{#each vm.relationProperties as rel (rel.id)}
						<option value={rel.id}>{rel.name}</option>
					{/each}
				</select>
				<select class="input" bind:value={rollupTargetPropId} data-testid="prop-rollup-target">
					<option value={TITLE_PROPERTY}>Title</option>
					{#each rollupTargetOptions as tp (tp.id)}
						<option value={tp.id}>{tp.name}</option>
					{/each}
				</select>
				<select class="input" bind:value={rollupFn} data-testid="prop-rollup-function">
					{#each ROLLUP_FUNCTIONS as fn (fn)}
						<option value={fn}>{fn}</option>
					{/each}
				</select>
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
	.add-view {
		padding: 6px 8px;
		color: var(--tx3);
	}
	.add-view:hover {
		color: var(--tx);
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
	.sel-col {
		min-width: 36px;
		width: 36px;
		text-align: center;
	}
	.table tbody tr.selected {
		background: var(--accbg);
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
	.fx-marker {
		color: var(--tx3);
		font-style: italic;
		font-weight: 700;
	}
	.formula-input {
		min-width: 260px;
		font-family: var(--font-mono, monospace);
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
	.error {
		margin-top: 10px;
		color: var(--rose);
	}
</style>
