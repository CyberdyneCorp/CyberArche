<script lang="ts">
	import { goto } from '$app/navigation';
	import type { Document } from '$lib/api/documents';
	import { documentTree } from '$lib/viewmodels/document-tree.svelte';
	import { linkIndex } from '$lib/viewmodels/link-index.svelte';

	let { workspaceId, onclose }: { workspaceId: string; onclose: () => void } = $props();

	let query = $state('');
	let selected = $state(0);

	const results = $derived(linkIndex.matches(query, 20));
	// A trailing "create" action appears when the query names no exact match.
	const canCreate = $derived(
		query.trim().length > 0 &&
			!results.some((d) => d.title.trim().toLowerCase() === query.trim().toLowerCase())
	);
	const count = $derived(results.length + (canCreate ? 1 : 0));

	$effect(() => {
		query; // reset highlight as the query changes
		selected = 0;
	});

	function open(doc: Document) {
		goto(`/w/${doc.workspace_id}/d/${doc.id}`);
		onclose();
	}

	async function create() {
		const created = await documentTree.create(query.trim());
		await linkIndex.refresh();
		goto(`/w/${created.workspace_id}/d/${created.id}`);
		onclose();
	}

	function activate(index: number) {
		if (index < results.length) open(results[index]);
		else if (canCreate) create();
	}

	function onkeydown(event: KeyboardEvent) {
		if (event.key === 'ArrowDown') {
			event.preventDefault();
			selected = Math.min(selected + 1, count - 1);
		} else if (event.key === 'ArrowUp') {
			event.preventDefault();
			selected = Math.max(selected - 1, 0);
		} else if (event.key === 'Enter') {
			event.preventDefault();
			activate(selected);
		} else if (event.key === 'Escape') {
			event.preventDefault();
			onclose();
		}
	}
</script>

<div class="backdrop" role="presentation" onclick={onclose}>
	<!-- svelte-ignore a11y_no_noninteractive_element_interactions, a11y_click_events_have_key_events -->
	<div
		class="palette"
		role="dialog"
		aria-modal="true"
		aria-label="Command palette"
		tabindex="-1"
		data-testid="command-palette"
		onclick={(e) => e.stopPropagation()}
	>
		<!-- svelte-ignore a11y_autofocus -->
		<input
			class="query"
			placeholder="Search documents or create one…"
			bind:value={query}
			{onkeydown}
			autofocus
			data-testid="palette-input"
		/>
		<div class="results" role="listbox">
			{#each results as doc, index (doc.id)}
				<button
					class="row"
					class:selected={index === selected}
					role="option"
					aria-selected={index === selected}
					data-testid="palette-result"
					onmousedown={(e) => {
						e.preventDefault();
						open(doc);
					}}
				>
					<span class="icon">▤</span>
					<span class="title">{doc.title || 'Untitled'}</span>
				</button>
			{/each}
			{#if canCreate}
				<button
					class="row create"
					class:selected={selected === results.length}
					role="option"
					aria-selected={selected === results.length}
					data-testid="palette-create"
					onmousedown={(e) => {
						e.preventDefault();
						create();
					}}
				>
					<span class="icon">＋</span>
					<span class="title">Create “{query.trim()}”</span>
				</button>
			{/if}
			{#if count === 0}
				<p class="none">No documents. Type a name to create one.</p>
			{/if}
		</div>
	</div>
</div>

<style>
	.backdrop {
		position: fixed;
		inset: 0;
		z-index: 1600;
		display: grid;
		place-items: start center;
		padding-top: 12vh;
		background: rgba(0, 0, 0, 0.35);
	}
	.palette {
		width: min(560px, 92vw);
		background: var(--bg1);
		border: 1px solid var(--line);
		border-radius: 12px;
		box-shadow: 0 24px 70px rgba(0, 0, 0, 0.35);
		overflow: hidden;
	}
	.query {
		width: 100%;
		border: none;
		outline: none;
		background: transparent;
		padding: 14px 16px;
		font-size: 15px;
		color: var(--tx);
		border-bottom: 1px solid var(--line);
	}
	.results {
		max-height: 50vh;
		overflow-y: auto;
		padding: 6px;
	}
	.row {
		display: flex;
		align-items: center;
		gap: 10px;
		width: 100%;
		padding: 8px 10px;
		border-radius: 8px;
		text-align: left;
	}
	.row.selected,
	.row:hover {
		background: var(--accbg);
	}
	.icon {
		color: var(--tx3);
		font-size: 12px;
	}
	.title {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.create .title {
		color: var(--acc-strong);
	}
	.none {
		margin: 10px;
		color: var(--tx3);
		font-size: 13px;
	}
</style>
