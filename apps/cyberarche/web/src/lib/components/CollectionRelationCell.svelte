<script lang="ts">
	import type { PropertyDef, RelatedRow } from '$lib/api/collections';

	let {
		property,
		value,
		relatedTitle = (id: string) => id,
		loadOptions,
		onchange
	}: {
		property: PropertyDef;
		value: unknown;
		/** Resolve a linked row id to its display title. */
		relatedTitle?: (id: string) => string;
		/** Load the target collection's rows for the picker. */
		loadOptions?: () => Promise<RelatedRow[]>;
		/** Persist the new set of linked ids. */
		onchange: (ids: string[]) => void;
	} = $props();

	const ids = $derived(Array.isArray(value) ? (value as string[]) : []);
	let open = $state(false);
	let options = $state<RelatedRow[]>([]);

	async function toggleOpen() {
		open = !open;
		if (open && loadOptions) options = await loadOptions();
	}

	function toggle(id: string) {
		const next = ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id];
		onchange(next);
	}
</script>

<div class="relation-cell" data-testid="cell-relation">
	<div class="chips">
		{#each ids as id (id)}
			<span class="chip" data-testid="relation-chip">{relatedTitle(id) || 'Untitled'}</span>
		{/each}
		<button
			type="button"
			class="relation-edit"
			data-testid="relation-edit"
			aria-label="Edit links for {property.name}"
			onclick={toggleOpen}>＋</button
		>
	</div>
	{#if open}
		<div class="picker" data-testid="relation-picker">
			{#each options as opt (opt.id)}
				<label class="picker-row">
					<input
						type="checkbox"
						checked={ids.includes(opt.id)}
						data-testid="relation-option"
						onchange={() => toggle(opt.id)}
					/>
					<span>{opt.title || 'Untitled'}</span>
				</label>
			{/each}
			{#if options.length === 0}
				<p class="picker-empty">No rows to link</p>
			{/if}
		</div>
	{/if}
</div>

<style>
	.relation-cell {
		position: relative;
	}
	.chips {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 4px;
	}
	.chip {
		display: inline-flex;
		align-items: center;
		padding: 1px 6px;
		border-radius: 10px;
		background: var(--accbg);
		color: var(--acc-strong);
		font-size: 12px;
	}
	.relation-edit {
		color: var(--tx3);
	}
	.relation-edit:hover {
		color: var(--tx);
	}
	.picker {
		position: absolute;
		z-index: 10;
		top: 100%;
		left: 0;
		min-width: 160px;
		margin-top: 4px;
		padding: 6px;
		border: 1px solid var(--line);
		border-radius: var(--r-control);
		background: var(--bg0);
		box-shadow: var(--shadow, 0 4px 12px rgba(0, 0, 0, 0.15));
		max-height: 220px;
		overflow-y: auto;
	}
	.picker-row {
		display: flex;
		align-items: center;
		gap: 6px;
		padding: 3px 4px;
		font-size: 13px;
		color: var(--tx);
	}
	.picker-empty {
		padding: 4px;
		color: var(--tx3);
		font-size: 12px;
	}
</style>
