<script lang="ts">
	import type { PropertyType } from '$lib/api/collections';
	import type { CollectionVM } from '$lib/viewmodels/collection.svelte';
	import { dialogs } from '$lib/viewmodels/dialogs.svelte';

	let { vm }: { vm: CollectionVM } = $props();

	// The simple, directly-settable property types the bulk control supports
	// (formula/rollup are read-only; relation/multi_select need richer editors).
	const SETTABLE: PropertyType[] = ['text', 'number', 'select', 'checkbox', 'date', 'url'];

	let propId = $state('');
	let value = $state<unknown>('');

	const settableProps = $derived(vm.properties.filter((p) => SETTABLE.includes(p.type)));
	const prop = $derived(vm.properties.find((p) => p.id === propId));

	/** Pick the target property and reset the value to that type's empty. */
	function pickProperty(id: string) {
		propId = id;
		const picked = vm.properties.find((p) => p.id === id);
		value = picked?.type === 'checkbox' ? false : '';
	}

	function applySet() {
		if (propId) vm.bulkSet(propId, value);
	}

	async function confirmDelete() {
		const ok = await dialogs.confirm({
			title: 'Delete rows',
			message: `Delete ${vm.selectedCount} selected row(s)? This cannot be undone.`,
			confirmLabel: 'Delete',
			danger: true
		});
		if (ok) await vm.bulkDelete();
	}
</script>

<div class="bulk-bar" data-testid="bulk-bar">
	<span class="count" data-testid="bulk-count">{vm.selectedCount} selected</span>

	<div class="set-control">
		<select
			class="input"
			data-testid="bulk-property"
			value={propId}
			onchange={(e) => pickProperty(e.currentTarget.value)}
		>
			<option value="">Set property…</option>
			{#each settableProps as p (p.id)}
				<option value={p.id}>{p.name}</option>
			{/each}
		</select>

		{#if prop}
			{#if prop.type === 'checkbox'}
				<input
					type="checkbox"
					data-testid="bulk-value-checkbox"
					checked={value === true}
					onchange={(e) => (value = e.currentTarget.checked)}
				/>
			{:else if prop.type === 'select'}
				<select
					class="input"
					data-testid="bulk-value-select"
					value={String(value ?? '')}
					onchange={(e) => (value = e.currentTarget.value)}
				>
					<option value="">—</option>
					{#each prop.options as option (option)}
						<option value={option}>{option}</option>
					{/each}
				</select>
			{:else if prop.type === 'number'}
				<input
					type="number"
					class="input"
					data-testid="bulk-value-number"
					value={String(value ?? '')}
					onchange={(e) => (value = e.currentTarget.value)}
				/>
			{:else if prop.type === 'date'}
				<input
					type="date"
					class="input"
					data-testid="bulk-value-date"
					value={String(value ?? '')}
					onchange={(e) => (value = e.currentTarget.value)}
				/>
			{:else}
				<input
					type="text"
					class="input"
					data-testid="bulk-value-text"
					value={String(value ?? '')}
					onchange={(e) => (value = e.currentTarget.value)}
				/>
			{/if}
			<button class="btn" data-testid="bulk-set" onclick={applySet}>Set</button>
		{/if}
	</div>

	<button class="btn danger" data-testid="bulk-delete" onclick={confirmDelete}>Delete</button>
	<button class="btn ghost" data-testid="bulk-clear" onclick={() => vm.clearSelection()}>Clear</button>
</div>

<style>
	.bulk-bar {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 8px;
		margin-bottom: 10px;
		padding: 8px 12px;
		border: 1px solid var(--line);
		border-radius: var(--r-control);
		background: var(--bg0);
	}
	.count {
		font-weight: 600;
		color: var(--tx);
	}
	.set-control {
		display: flex;
		align-items: center;
		gap: 6px;
	}
	.input {
		padding: 5px 8px;
		border: 1px solid var(--line);
		border-radius: var(--r-control);
		background: var(--bg);
		color: var(--tx);
	}
	.btn {
		padding: 5px 12px;
		border-radius: var(--r-control);
		background: var(--acc);
		color: #fff;
		font-weight: 500;
	}
	.btn.danger {
		background: var(--rose);
	}
	.btn.ghost {
		background: transparent;
		color: var(--tx2);
		border: 1px solid var(--line);
	}
</style>
