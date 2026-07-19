<script lang="ts">
	import type { PropertyDef, RelatedRow } from '$lib/api/collections';
	import CollectionRelationCell from './CollectionRelationCell.svelte';

	let {
		property,
		value,
		onchange,
		relatedTitle,
		loadRelationOptions,
		readOnly = false
	}: {
		property: PropertyDef;
		value: unknown;
		onchange: (value: unknown) => void;
		/** Relation only: resolve a linked row id to its title. */
		relatedTitle?: (id: string) => string;
		/** Relation only: load the target collection's rows for the picker. */
		loadRelationOptions?: () => Promise<RelatedRow[]>;
		/** Render the value without any editor (embedded read-only databases). */
		readOnly?: boolean;
	} = $props();

	const asText = (v: unknown): string => (v === null || v === undefined ? '' : String(v));
	const asList = (v: unknown): string[] => (Array.isArray(v) ? (v as string[]) : []);

	/** A plain, non-editable rendering of the cell value for read-only mode. */
	function displayText(): string {
		if (property.type === 'checkbox') return value === true ? '✓' : '';
		if (property.type === 'relation')
			return asList(value)
				.map((id) => relatedTitle?.(id) ?? id)
				.join(', ');
		if (property.type === 'multi_select') return asList(value).join(', ');
		return asText(value);
	}

	function addTag(option: string) {
		if (!option) return;
		const current = asList(value);
		if (!current.includes(option)) onchange([...current, option]);
	}

	function removeTag(option: string) {
		onchange(asList(value).filter((t) => t !== option));
	}
</script>

{#if readOnly}
	<!-- Embedded read-only database: show the value, never an editor. -->
	<span class="formula-value" data-testid="cell-readonly">{displayText()}</span>
{:else if property.type === 'formula'}
	<!-- Read-only: the computed value arrives in the row's properties from
	     queryView. No editor, and no setRowValues on interaction. -->
	<span class="formula-value" data-testid="cell-formula">{asText(value)}</span>
{:else if property.type === 'rollup'}
	<!-- Read-only: the aggregate arrives in the row's properties from queryView. -->
	<span class="formula-value" data-testid="cell-rollup">{asText(value)}</span>
{:else if property.type === 'relation'}
	<CollectionRelationCell
		{property}
		{value}
		{relatedTitle}
		loadOptions={loadRelationOptions}
		onchange={(ids) => onchange(ids)}
	/>
{:else if property.type === 'checkbox'}
	<input
		type="checkbox"
		checked={value === true}
		data-testid="cell-checkbox"
		onchange={(e) => onchange(e.currentTarget.checked)}
	/>
{:else if property.type === 'select'}
	<select
		class="cell-input"
		value={asText(value)}
		data-testid="cell-select"
		onchange={(e) => onchange(e.currentTarget.value || null)}
	>
		<option value="">—</option>
		{#each property.options as option (option)}
			<option value={option}>{option}</option>
		{/each}
	</select>
{:else if property.type === 'multi_select'}
	<div class="chips" data-testid="cell-multi-select">
		{#each asList(value) as tag (tag)}
			<span class="chip">
				{tag}
				<button type="button" class="chip-x" onclick={() => removeTag(tag)} aria-label="Remove {tag}"
					>×</button
				>
			</span>
		{/each}
		<select class="cell-input" value="" onchange={(e) => { addTag(e.currentTarget.value); e.currentTarget.value = ''; }}>
			<option value="">＋</option>
			{#each property.options.filter((o) => !asList(value).includes(o)) as option (option)}
				<option value={option}>{option}</option>
			{/each}
		</select>
	</div>
{:else if property.type === 'number'}
	<input
		type="number"
		class="cell-input"
		value={asText(value)}
		data-testid="cell-number"
		onchange={(e) => onchange(e.currentTarget.value === '' ? null : e.currentTarget.value)}
	/>
{:else if property.type === 'date'}
	<input
		type="date"
		class="cell-input"
		value={asText(value)}
		data-testid="cell-date"
		onchange={(e) => onchange(e.currentTarget.value || null)}
	/>
{:else if property.type === 'url'}
	<div class="url-cell">
		<input
			type="url"
			class="cell-input"
			value={asText(value)}
			data-testid="cell-url"
			onchange={(e) => onchange(e.currentTarget.value || null)}
		/>
		{#if asText(value)}
			<a class="url-open" href={asText(value)} target="_blank" rel="noreferrer noopener">↗</a>
		{/if}
	</div>
{:else}
	<input
		type="text"
		class="cell-input"
		value={asText(value)}
		data-testid="cell-text"
		onchange={(e) => onchange(e.currentTarget.value)}
	/>
{/if}

<style>
	.cell-input {
		width: 100%;
		border: none;
		background: transparent;
		color: var(--tx);
		font: inherit;
		padding: 2px 4px;
	}
	.formula-value {
		display: inline-block;
		width: 100%;
		padding: 2px 4px;
		color: var(--tx2);
	}
	.cell-input:focus {
		outline: 1px solid var(--acc);
		border-radius: 4px;
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
		gap: 3px;
		padding: 1px 6px;
		border-radius: 10px;
		background: var(--accbg);
		color: var(--acc-strong);
		font-size: 12px;
	}
	.chip-x {
		color: var(--tx3);
		line-height: 1;
	}
	.url-cell {
		display: flex;
		align-items: center;
		gap: 4px;
	}
	.url-open {
		color: var(--acc-strong);
		text-decoration: none;
	}
</style>
