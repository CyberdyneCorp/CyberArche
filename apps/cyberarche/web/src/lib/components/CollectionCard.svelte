<script lang="ts">
	import type { CollectionRow, PropertyDef } from '$lib/api/collections';

	let {
		row,
		properties,
		onOpenRow
	}: {
		row: CollectionRow;
		/** Properties to show on the card (read-only). */
		properties: PropertyDef[];
		/** Open the row as a full document page. */
		onOpenRow: (rowId: string) => void;
	} = $props();

	function display(value: unknown): string {
		if (value === null || value === undefined || value === '') return '';
		if (Array.isArray(value)) return value.join(', ');
		if (typeof value === 'boolean') return value ? '✓' : '';
		return String(value);
	}

	const fields = $derived(
		properties
			.map((p) => ({ id: p.id, name: p.name, text: display(row.properties[p.id]) }))
			.filter((f) => f.text !== '')
	);
</script>

<div class="card" data-testid="collection-card">
	<button class="card-title" data-testid="card-title" onclick={() => onOpenRow(row.id)}>
		{row.title || 'Untitled'}
	</button>
	{#if fields.length > 0}
		<dl class="fields">
			{#each fields as field (field.id)}
				<div class="field">
					<dt>{field.name}</dt>
					<dd>{field.text}</dd>
				</div>
			{/each}
		</dl>
	{/if}
</div>

<style>
	.card {
		display: flex;
		flex-direction: column;
		gap: 6px;
		padding: 10px 12px;
		background: var(--bg1, #fff);
		border: 1px solid var(--line);
		border-radius: 8px;
	}
	.card-title {
		text-align: left;
		font-weight: 600;
		color: var(--tx);
		font-size: 14px;
		line-height: 1.3;
	}
	.card-title:hover {
		color: var(--acc-strong);
	}
	.fields {
		display: flex;
		flex-direction: column;
		gap: 3px;
		margin: 0;
	}
	.field {
		display: flex;
		gap: 6px;
		font-size: 12px;
	}
	.field dt {
		flex: 0 0 auto;
		color: var(--tx3);
	}
	.field dd {
		margin: 0;
		color: var(--tx2);
		min-width: 0;
		overflow-wrap: anywhere;
	}
</style>
