<script lang="ts">
	/** Database block (database-block spec): a schema of typed properties + rows,
	 * shown as an editable Table or a kanban Board grouped by a select property.
	 * State lives in the document CRDT via the database view-model. */
	import type { BlockComponentProps } from '$lib/editor/registry';
	import type { EditorVM } from '$lib/viewmodels/editor.svelte';
	import {
		applyFilters,
		createDatabase,
		OPERATORS,
		sortRows,
		type DatabaseVM,
		type DbSnapshot,
		type Property,
		type PropertyType,
		type Row
	} from '$lib/viewmodels/database.svelte';

	let { block, editor }: BlockComponentProps = $props();
	const vm = editor as EditorVM;
	const ro = $derived(vm.readOnly);

	const db: DatabaseVM = createDatabase(vm.doc, block.id, {
		initial: block.data.db as DbSnapshot | undefined,
		onMirror: (snapshot) => vm.updateData(block.id, { db: snapshot })
	});
	$effect(() => () => db.destroy());

	let view = $state<'table' | 'board'>('table');
	let sort = $state<{ id: string; dir: 'asc' | 'desc' } | null>(null);
	let optionsFor = $state<string | null>(null); // property id whose options popover is open
	let newOption = $state('');
	let filtersOpen = $state(false);

	const propById = $derived(new Map(db.properties.map((p) => [p.id, p])));
	function opsFor(propertyId: string) {
		const p = propById.get(propertyId);
		return p ? OPERATORS[p.type] : OPERATORS.text;
	}
	function needsValue(propertyId: string, op: string): boolean {
		return opsFor(propertyId).find((o) => o.value === op)?.needsValue ?? false;
	}

	const TYPES: { value: PropertyType; label: string }[] = [
		{ value: 'text', label: 'Text' },
		{ value: 'number', label: 'Number' },
		{ value: 'select', label: 'Select' },
		{ value: 'checkbox', label: 'Checkbox' },
		{ value: 'date', label: 'Date' }
	];

	const selectProps = $derived(db.properties.filter((p) => p.type === 'select'));
	let boardProp = $state<string>('');
	$effect(() => {
		// Default the board grouping to the first select property.
		if (!boardProp && selectProps.length) boardProp = selectProps[0].id;
	});

	const filteredRows = $derived(applyFilters(db.rows, db.filters, db.properties));
	const displayRows = $derived(
		sort ? sortRows(filteredRows, sort.id, sort.dir) : filteredRows
	);
	const boardGroups = $derived.by(() => {
		const groups = new Map<string, Row[]>();
		for (const row of filteredRows) {
			const key = (row.values[boardProp] as string) || '';
			(groups.get(key) ?? groups.set(key, []).get(key)!).push(row);
		}
		return groups;
	});

	function toggleSort(id: string): void {
		if (sort?.id !== id) sort = { id, dir: 'asc' };
		else if (sort.dir === 'asc') sort = { id, dir: 'desc' };
		else sort = null;
	}
	function optionName(prop: Property, id: unknown): string {
		return prop.options?.find((o) => o.id === id)?.name ?? '';
	}
	function optionColor(prop: Property, id: unknown): string {
		return prop.options?.find((o) => o.id === id)?.color ?? 'var(--tx3)';
	}
	function addOption(propId: string): void {
		const name = newOption.trim();
		if (!name) return;
		db.addOption(propId, name);
		newOption = '';
	}
	// ---- board ----
	const boardProperty = $derived(db.properties.find((p) => p.id === boardProp));
	const titleProp = $derived(db.properties.find((p) => p.type === 'text') ?? db.properties[0]);
	function cardTitle(row: Row): string {
		return (titleProp && (row.values[titleProp.id] as string)) || 'Untitled';
	}
	let dragRow: string | null = null;
	function onDrop(optionId: string): void {
		if (dragRow && boardProp) db.setCell(dragRow, boardProp, optionId || null);
		dragRow = null;
	}
</script>

<div class="db" data-testid="database-block">
	<header class="bar">
		<div class="views">
			<button class:active={view === 'table'} onclick={() => (view = 'table')}>▦ Table</button>
			<button class:active={view === 'board'} onclick={() => (view = 'board')} disabled={!selectProps.length}>▧ Board</button>
		</div>
		{#if view === 'board' && selectProps.length}
			<label class="group-by">
				Group by
				<select bind:value={boardProp}>
					{#each selectProps as p (p.id)}<option value={p.id}>{p.name}</option>{/each}
				</select>
			</label>
		{/if}
		{#if !ro}
			<div class="filter-wrap">
				<button
					class="filter-btn"
					class:on={db.filters.length > 0}
					data-testid="db-filter"
					onclick={() => (filtersOpen = !filtersOpen)}
					>⚑ Filter{db.filters.length ? ` (${db.filters.length})` : ''}</button
				>
				{#if filtersOpen}
					<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
					<div class="filter-scrim" role="presentation" onclick={() => (filtersOpen = false)}></div>
					<div class="filter-pop">
						{#each db.filters as f (f.id)}
							{@const p = propById.get(f.propertyId)}
							<div class="filter-row">
								<select value={f.propertyId} onchange={(e) => {
									const pid = (e.target as HTMLSelectElement).value;
									db.updateFilter(f.id, { propertyId: pid, op: opsFor(pid)[0].value, value: null });
								}}>
									{#each db.properties as prop (prop.id)}<option value={prop.id}>{prop.name}</option>{/each}
								</select>
								<select value={f.op} onchange={(e) => db.updateFilter(f.id, { op: (e.target as HTMLSelectElement).value })}>
									{#each opsFor(f.propertyId) as o (o.value)}<option value={o.value}>{o.label}</option>{/each}
								</select>
								{#if needsValue(f.propertyId, f.op)}
									{#if p?.type === 'select'}
										<select value={(f.value as string) ?? ''} onchange={(e) => db.updateFilter(f.id, { value: (e.target as HTMLSelectElement).value || null })}>
											<option value="">—</option>
											{#each p.options ?? [] as o (o.id)}<option value={o.id}>{o.name}</option>{/each}
										</select>
									{:else}
										<input
											type={p?.type === 'number' ? 'number' : p?.type === 'date' ? 'date' : 'text'}
											value={(f.value as string | number) ?? ''}
											oninput={(e) => db.updateFilter(f.id, { value: (e.target as HTMLInputElement).value })}
										/>
									{/if}
								{/if}
								<button class="mini danger" title="Remove" onclick={() => db.removeFilter(f.id)}>×</button>
							</div>
						{/each}
						<button class="add-filter" onclick={() => db.addFilter()}>＋ Add filter</button>
					</div>
				{/if}
			</div>
		{/if}
	</header>

	{#if view === 'table'}
		<div class="scroll">
			<table>
				<thead>
					<tr>
						<th class="gutter"></th>
						{#each db.properties as p (p.id)}
							<th>
								<div class="col">
									{#if ro}
										<span class="col-name">{p.name}</span>
									{:else}
										<input class="col-name" value={p.name} oninput={(e) => db.renameProperty(p.id, (e.target as HTMLInputElement).value)} />
										<select class="col-type" value={p.type} onchange={(e) => db.setPropertyType(p.id, (e.target as HTMLSelectElement).value as PropertyType)}>
											{#each TYPES as t (t.value)}<option value={t.value}>{t.label}</option>{/each}
										</select>
										{#if p.type === 'select'}
											<button class="mini" title="Options" onclick={() => (optionsFor = optionsFor === p.id ? null : p.id)}>⚙</button>
										{/if}
										<button class="sort" onclick={() => toggleSort(p.id)}>{sort?.id === p.id ? (sort.dir === 'asc' ? '↑' : '↓') : '↕'}</button>
										<button class="mini danger" title="Delete column" onclick={() => db.removeProperty(p.id)}>×</button>
									{/if}
								</div>
								{#if optionsFor === p.id && p.type === 'select'}
									<div class="options-pop">
										{#each p.options ?? [] as o (o.id)}
											<span class="opt"><span class="dot" style={`background:${o.color}`}></span>{o.name}</span>
										{/each}
										<input placeholder="Add option…" bind:value={newOption} onkeydown={(e) => e.key === 'Enter' && addOption(p.id)} />
									</div>
								{/if}
							</th>
						{/each}
						{#if !ro}
							<th class="add-col"><button title="Add column" onclick={() => db.addProperty('text')}>＋</button></th>
						{/if}
					</tr>
				</thead>
				<tbody>
					{#each displayRows as row (row.id)}
						<tr>
							<td class="gutter">
								{#if !ro}<button class="row-del" title="Delete row" onclick={() => db.removeRow(row.id)}>×</button>{/if}
							</td>
							{#each db.properties as p (p.id)}
								<td>
									{#if p.type === 'checkbox'}
										<input type="checkbox" checked={!!row.values[p.id]} disabled={ro} onchange={(e) => db.setCell(row.id, p.id, (e.target as HTMLInputElement).checked)} />
									{:else if p.type === 'number'}
										<input class="cell" type="number" value={(row.values[p.id] as number) ?? ''} disabled={ro} oninput={(e) => db.setCell(row.id, p.id, (e.target as HTMLInputElement).value === '' ? null : Number((e.target as HTMLInputElement).value))} />
									{:else if p.type === 'date'}
										<input class="cell" type="date" value={(row.values[p.id] as string) ?? ''} disabled={ro} onchange={(e) => db.setCell(row.id, p.id, (e.target as HTMLInputElement).value || null)} />
									{:else if p.type === 'select'}
										<select class="cell select" value={(row.values[p.id] as string) ?? ''} disabled={ro} onchange={(e) => db.setCell(row.id, p.id, (e.target as HTMLSelectElement).value || null)} style={row.values[p.id] ? `color:${optionColor(p, row.values[p.id])}` : ''}>
											<option value="">—</option>
											{#each p.options ?? [] as o (o.id)}<option value={o.id}>{o.name}</option>{/each}
										</select>
									{:else}
										<input class="cell" value={(row.values[p.id] as string) ?? ''} disabled={ro} oninput={(e) => db.setCell(row.id, p.id, (e.target as HTMLInputElement).value)} />
									{/if}
								</td>
							{/each}
							{#if !ro}<td></td>{/if}
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
		{#if !ro}
			<button class="add-row" data-testid="db-add-row" onclick={() => db.addRow()}>＋ New row</button>
		{/if}
	{:else if boardProperty}
		<div class="board">
			{#each [...(boardProperty.options ?? []), { id: '', name: 'No ' + boardProperty.name, color: 'var(--tx3)' }] as col (col.id)}
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<div class="board-col" ondragover={(e) => e.preventDefault()} ondrop={() => onDrop(col.id)}>
					<div class="col-head"><span class="dot" style={`background:${col.color}`}></span>{col.name}<span class="count">{boardGroups.get(col.id)?.length ?? 0}</span></div>
					{#each boardGroups.get(col.id) ?? [] as row (row.id)}
						<!-- svelte-ignore a11y_no_static_element_interactions -->
						<div class="card" draggable={!ro} ondragstart={() => (dragRow = row.id)} data-testid="db-card">{cardTitle(row)}</div>
					{/each}
					{#if !ro}
						<button class="add-card" onclick={() => db.addRow(col.id ? { [boardProp]: col.id } : {})}>＋ Add</button>
					{/if}
				</div>
			{/each}
		</div>
	{/if}
</div>

<style>
	.db {
		background: var(--bg2);
		border: 1px solid var(--line);
		border-radius: var(--r-block);
		overflow: hidden;
	}
	.bar {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 6px 10px;
		border-bottom: 1px solid var(--line);
	}
	.views {
		display: flex;
		gap: 2px;
	}
	.views button {
		padding: 3px 9px;
		border-radius: var(--r-control);
		color: var(--tx2);
		font-size: 12px;
	}
	.views button.active {
		background: var(--accbg2);
		color: var(--acc-strong);
	}
	.views button:disabled {
		opacity: 0.4;
	}
	.group-by {
		font-size: 12px;
		color: var(--tx2);
		display: flex;
		align-items: center;
		gap: 5px;
	}
	.filter-wrap {
		position: relative;
		margin-left: auto;
	}
	.filter-btn {
		padding: 3px 9px;
		border-radius: var(--r-control);
		border: 1px solid var(--line);
		color: var(--tx2);
		font-size: 12px;
	}
	.filter-btn:hover {
		background: var(--bg3);
		color: var(--tx);
	}
	.filter-btn.on {
		background: var(--accbg2);
		border-color: var(--acc);
		color: var(--acc-strong);
	}
	.filter-scrim {
		position: fixed;
		inset: 0;
		z-index: 9;
	}
	.filter-pop {
		position: absolute;
		top: calc(100% + 6px);
		right: 0;
		z-index: 10;
		width: 340px;
		max-width: 86vw;
		padding: 10px;
		background: var(--bg1);
		border: 1px solid var(--line);
		border-radius: 10px;
		box-shadow: var(--sh3);
		display: flex;
		flex-direction: column;
		gap: 6px;
	}
	.filter-row {
		display: flex;
		gap: 5px;
		align-items: center;
	}
	.filter-row select,
	.filter-row input {
		flex: 1;
		min-width: 0;
		font-size: 12px;
		padding: 4px 6px;
		border: 1px solid var(--line);
		border-radius: 6px;
		background: var(--bg2);
		color: var(--tx);
	}
	.add-filter {
		text-align: left;
		color: var(--acc);
		font-size: 12.5px;
		padding: 4px 2px;
	}
	.group-by select,
	.col-type {
		font-size: 11px;
		border: 1px solid var(--line);
		border-radius: 5px;
		background: var(--bg1);
		color: var(--tx2);
		padding: 1px 3px;
	}
	.scroll {
		overflow-x: auto;
	}
	table {
		border-collapse: collapse;
		width: 100%;
		font-size: 13px;
	}
	th,
	td {
		border: 1px solid var(--line);
		padding: 0;
		text-align: left;
		vertical-align: top;
	}
	.gutter {
		width: 24px;
		background: var(--bg1);
	}
	.col {
		display: flex;
		align-items: center;
		gap: 3px;
		padding: 4px 6px;
		position: relative;
	}
	.col-name {
		flex: 1;
		min-width: 70px;
		border: none;
		background: transparent;
		color: var(--tx);
		font-weight: 600;
		font-size: 12.5px;
	}
	.mini,
	.sort {
		color: var(--tx3);
		padding: 1px 4px;
		border-radius: 4px;
		font-size: 11px;
	}
	.mini:hover,
	.sort:hover {
		background: var(--bg3);
		color: var(--tx);
	}
	.mini.danger:hover {
		color: var(--rose);
	}
	.options-pop {
		position: absolute;
		top: 100%;
		left: 6px;
		z-index: 5;
		display: flex;
		flex-direction: column;
		gap: 4px;
		padding: 8px;
		background: var(--bg1);
		border: 1px solid var(--line);
		border-radius: 8px;
		box-shadow: var(--sh3);
		min-width: 140px;
	}
	.opt {
		display: flex;
		align-items: center;
		gap: 6px;
		font-size: 12px;
		color: var(--tx);
	}
	.dot {
		width: 9px;
		height: 9px;
		border-radius: 50%;
		display: inline-block;
		flex-shrink: 0;
	}
	.cell {
		width: 100%;
		border: none;
		background: transparent;
		color: var(--tx);
		padding: 5px 6px;
		font-size: 13px;
	}
	.cell:focus {
		outline: 1.5px solid var(--acc);
		outline-offset: -1px;
	}
	.select {
		appearance: none;
	}
	td input[type='checkbox'] {
		margin: 6px;
	}
	.row-del {
		width: 100%;
		color: var(--tx3);
		font-size: 13px;
	}
	.row-del:hover {
		color: var(--rose);
	}
	.add-col button {
		width: 30px;
		color: var(--tx3);
		padding: 5px;
	}
	.add-row {
		display: block;
		width: 100%;
		text-align: left;
		padding: 7px 12px;
		color: var(--tx2);
		font-size: 12.5px;
		border-top: 1px solid var(--line);
	}
	.add-row:hover {
		background: var(--bg3);
		color: var(--tx);
	}
	.board {
		display: flex;
		gap: 10px;
		padding: 12px;
		overflow-x: auto;
		align-items: flex-start;
	}
	.board-col {
		flex: 0 0 200px;
		background: var(--bg1);
		border: 1px solid var(--line);
		border-radius: 8px;
		padding: 8px;
		display: flex;
		flex-direction: column;
		gap: 6px;
		min-height: 60px;
	}
	.col-head {
		display: flex;
		align-items: center;
		gap: 6px;
		font-size: 12px;
		font-weight: 600;
		color: var(--tx);
	}
	.count {
		margin-left: auto;
		color: var(--tx3);
		font-weight: 400;
	}
	.card {
		background: var(--bg2);
		border: 1px solid var(--line);
		border-radius: 6px;
		padding: 8px 9px;
		font-size: 12.5px;
		color: var(--tx);
		cursor: grab;
	}
	.card:active {
		cursor: grabbing;
	}
	.add-card {
		text-align: left;
		color: var(--tx3);
		font-size: 12px;
		padding: 3px 4px;
	}
	.add-card:hover {
		color: var(--tx);
	}
</style>
