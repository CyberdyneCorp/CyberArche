<script lang="ts">
	import type { BlockComponentProps } from '$lib/editor/registry';
	import type { EditorVM } from '$lib/viewmodels/editor.svelte';
	import EditableText from '../EditableText.svelte';

	let { block, editor }: BlockComponentProps = $props();
	const vm = editor as EditorVM;

	const header = $derived((block.data.header as string[]) ?? []);
	const rows = $derived((block.data.rows as string[][]) ?? []);

	function setHeader(column: number, value: string) {
		const next = [...header];
		next[column] = value;
		vm.updateData(block.id, { header: next });
	}
	function setCell(row: number, column: number, value: string) {
		const next = rows.map((r) => [...r]);
		next[row][column] = value;
		vm.updateData(block.id, { rows: next });
	}
	function addRow() {
		vm.updateData(block.id, { rows: [...rows, header.map(() => '')] });
	}
	function removeRow(index: number) {
		vm.updateData(block.id, { rows: rows.filter((_, i) => i !== index) });
	}
	function addColumn() {
		vm.updateData(block.id, {
			header: [...header, `Column ${header.length + 1}`],
			rows: rows.map((row) => [...row, ''])
		});
	}
	function removeColumn(column: number) {
		if (header.length <= 1) return;
		vm.updateData(block.id, {
			header: header.filter((_, i) => i !== column),
			rows: rows.map((row) => row.filter((_, i) => i !== column))
		});
	}
</script>

<div class="table-block" data-testid="table-block">
	<table>
		<thead>
			<tr>
				{#each header as cell, column (column)}
					<th>
						<div class="cell">
							<EditableText
								value={cell}
								rich
								syncSignal={vm.historyRevision}
								onchange={(next) => setHeader(column, next)}
								onfocus={() => vm.focus(block.id)}
							/>
						</div>
						<button
							class="col-remove"
							title="Remove column"
							onclick={() => removeColumn(column)}>×</button
						>
					</th>
				{/each}
				<th class="add-cell">
					<button title="Add column" data-testid="add-column" onclick={addColumn}>＋</button>
				</th>
			</tr>
		</thead>
		<tbody>
			{#each rows as row, rowIndex (rowIndex)}
				<tr>
					{#each row as cell, column (column)}
						<td>
							<div class="cell">
								<EditableText
									value={cell}
									rich
									syncSignal={vm.historyRevision}
									onchange={(next) => setCell(rowIndex, column, next)}
									onfocus={() => vm.focus(block.id)}
								/>
							</div>
						</td>
					{/each}
					<td class="add-cell">
						<button title="Remove row" onclick={() => removeRow(rowIndex)}>×</button>
					</td>
				</tr>
			{/each}
		</tbody>
	</table>
	<button class="add-row" data-testid="add-row" onclick={addRow}>＋ Row</button>
</div>

<style>
	.table-block {
		overflow-x: auto;
	}
	table {
		border-collapse: collapse;
		width: 100%;
	}
	th,
	td {
		border: 1px solid var(--line2);
		padding: 0;
		position: relative;
	}
	th {
		background: var(--bg2);
	}
	.cell :global(.editable) {
		width: 100%;
		outline: none;
		padding: 7px 10px;
		font-size: 13.5px;
	}
	th .cell :global(.editable) {
		font-weight: 600;
	}
	.add-cell {
		border: none;
		background: none;
		width: 28px;
		text-align: center;
	}
	.add-cell button,
	.col-remove {
		color: var(--tx3);
		padding: 2px 6px;
	}
	.add-cell button:hover,
	.col-remove:hover {
		color: var(--tx);
	}
	.col-remove {
		position: absolute;
		right: 0;
		top: 2px;
		visibility: hidden;
	}
	th:hover .col-remove {
		visibility: visible;
	}
	.add-row {
		margin-top: 6px;
		color: var(--tx3);
		font-size: 12px;
	}
	.add-row:hover {
		color: var(--tx);
	}
</style>
