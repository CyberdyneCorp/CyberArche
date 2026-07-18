<script lang="ts">
	import type { Filter, PropertyDef } from '$lib/api/collections';
	import { operatorsForType } from '$lib/viewmodels/collection.svelte';

	let {
		filter,
		properties,
		onchange,
		onremove
	}: {
		filter: Filter;
		/** Pickable properties: the schema plus the synthetic Title property. */
		properties: PropertyDef[];
		onchange: (patch: Partial<Filter>) => void;
		onremove: () => void;
	} = $props();

	const selected = $derived(
		properties.find((p) => p.id === filter.property_id) ?? properties[0]
	);
	const ops = $derived(operatorsForType(selected.type));
	const needsValue = $derived(filter.op !== 'is_empty' && filter.op !== 'not_empty');

	const asText = (v: unknown): string => (v === null || v === undefined ? '' : String(v));

	function changeProperty(propertyId: string) {
		const prop = properties.find((p) => p.id === propertyId);
		const op = operatorsForType(prop?.type ?? 'text')[0].value;
		onchange({ property_id: propertyId, op, value: null });
	}
</script>

<div class="rule" data-testid="filter-rule">
	<select
		class="control"
		value={filter.property_id}
		data-testid="filter-property"
		onchange={(e) => changeProperty(e.currentTarget.value)}
	>
		{#each properties as prop (prop.id)}
			<option value={prop.id}>{prop.name}</option>
		{/each}
	</select>

	<select
		class="control"
		value={filter.op}
		data-testid="filter-op"
		onchange={(e) => onchange({ op: e.currentTarget.value })}
	>
		{#each ops as op (op.value)}
			<option value={op.value}>{op.label}</option>
		{/each}
	</select>

	{#if needsValue}
		{#if selected.type === 'checkbox'}
			<select
				class="control"
				value={filter.value === true ? 'true' : 'false'}
				data-testid="filter-value"
				onchange={(e) => onchange({ value: e.currentTarget.value === 'true' })}
			>
				<option value="true">checked</option>
				<option value="false">unchecked</option>
			</select>
		{:else if selected.type === 'select' || selected.type === 'multi_select'}
			<select
				class="control"
				value={asText(filter.value)}
				data-testid="filter-value"
				onchange={(e) => onchange({ value: e.currentTarget.value || null })}
			>
				<option value="">—</option>
				{#each selected.options as option (option)}
					<option value={option}>{option}</option>
				{/each}
			</select>
		{:else if selected.type === 'number'}
			<input
				class="control"
				type="number"
				value={asText(filter.value)}
				data-testid="filter-value"
				onchange={(e) => onchange({ value: e.currentTarget.value === '' ? null : e.currentTarget.value })}
			/>
		{:else if selected.type === 'date'}
			<input
				class="control"
				type="date"
				value={asText(filter.value)}
				data-testid="filter-value"
				onchange={(e) => onchange({ value: e.currentTarget.value || null })}
			/>
		{:else}
			<input
				class="control"
				type="text"
				value={asText(filter.value)}
				data-testid="filter-value"
				placeholder="Value"
				onchange={(e) => onchange({ value: e.currentTarget.value })}
			/>
		{/if}
	{/if}

	<button class="remove" data-testid="filter-remove" title="Remove filter" onclick={onremove}
		>×</button
	>
</div>

<style>
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
	.remove {
		color: var(--tx3);
		font-size: 15px;
		line-height: 1;
		padding: 2px 4px;
		flex: 0 0 auto;
	}
	.remove:hover {
		color: var(--rose);
	}
</style>
