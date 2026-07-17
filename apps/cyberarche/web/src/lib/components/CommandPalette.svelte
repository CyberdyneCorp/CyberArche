<script lang="ts">
	import { goto } from '$app/navigation';
	import type { Document } from '$lib/api/documents';
	import { askKnowledge, searchContent, type SearchHit } from '$lib/api/search';
	import { documentTree } from '$lib/viewmodels/document-tree.svelte';
	import { linkIndex } from '$lib/viewmodels/link-index.svelte';

	let { workspaceId, onclose }: { workspaceId: string; onclose: () => void } = $props();

	let query = $state('');
	let selected = $state(0);
	let contentHits = $state<SearchHit[]>([]);
	let answer = $state<string | null>(null);
	let asking = $state(false);

	const titleResults = $derived(linkIndex.matches(query, 20));
	// A trailing "create" action appears when the query names no exact match.
	const canCreate = $derived(
		query.trim().length > 0 &&
			!titleResults.some((d) => d.title.trim().toLowerCase() === query.trim().toLowerCase())
	);

	// One flat list drives rendering and keyboard nav: title matches, then
	// content matches, then create, then the "Ask AI" row.
	type Item =
		| { kind: 'doc'; doc: Document }
		| { kind: 'content'; hit: SearchHit }
		| { kind: 'create' }
		| { kind: 'ask' };

	const items = $derived.by<Item[]>(() => {
		const list: Item[] = titleResults.map((doc) => ({ kind: 'doc', doc }));
		for (const hit of contentHits) list.push({ kind: 'content', hit });
		if (canCreate) list.push({ kind: 'create' });
		if (query.trim().length > 0) list.push({ kind: 'ask' });
		return list;
	});

	$effect(() => {
		query; // reset highlight + any prior answer as the query changes
		selected = 0;
		answer = null;
	});

	// Content search is debounced; title matches stay instant (they are local).
	$effect(() => {
		const q = query.trim();
		if (!q) {
			contentHits = [];
			return;
		}
		const handle = setTimeout(async () => {
			const hits = await searchContent(workspaceId, q);
			contentHits = hits.filter((h) => h.field === 'content');
		}, 200);
		return () => clearTimeout(handle);
	});

	function openDocument(id: string) {
		goto(`/w/${workspaceId}/d/${id}`);
		onclose();
	}

	async function create() {
		const created = await documentTree.create(query.trim());
		await linkIndex.refresh();
		goto(`/w/${created.workspace_id}/d/${created.id}`);
		onclose();
	}

	async function ask() {
		asking = true;
		answer = null;
		try {
			const { result } = await askKnowledge(workspaceId, query.trim());
			answer = result;
		} finally {
			asking = false;
		}
	}

	function activate(index: number) {
		const item = items[index];
		if (!item) return;
		if (item.kind === 'doc') openDocument(item.doc.id);
		else if (item.kind === 'content') openDocument(item.hit.id);
		else if (item.kind === 'create') create();
		else ask();
	}

	function onkeydown(event: KeyboardEvent) {
		if (event.key === 'ArrowDown') {
			event.preventDefault();
			selected = Math.min(selected + 1, items.length - 1);
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
			{#each items as item, index (item.kind + ':' + index)}
				{#if item.kind === 'doc'}
					<button
						class="row"
						class:selected={index === selected}
						role="option"
						aria-selected={index === selected}
						data-testid="palette-result"
						onmousedown={(e) => {
							e.preventDefault();
							openDocument(item.doc.id);
						}}
					>
						<span class="icon">▤</span>
						<span class="title">{item.doc.title || 'Untitled'}</span>
					</button>
				{:else if item.kind === 'content'}
					<button
						class="row content"
						class:selected={index === selected}
						role="option"
						aria-selected={index === selected}
						data-testid="palette-content-result"
						onmousedown={(e) => {
							e.preventDefault();
							openDocument(item.hit.id);
						}}
					>
						<span class="icon">¶</span>
						<span class="body">
							<span class="title">{item.hit.title || 'Untitled'}</span>
							<span class="snippet">{item.hit.snippet}</span>
						</span>
						<span class="label">in text</span>
					</button>
				{:else if item.kind === 'create'}
					<button
						class="row create"
						class:selected={index === selected}
						role="option"
						aria-selected={index === selected}
						data-testid="palette-create"
						onmousedown={(e) => {
							e.preventDefault();
							create();
						}}
					>
						<span class="icon">＋</span>
						<span class="title">Create “{query.trim()}”</span>
					</button>
				{:else}
					<button
						class="row ask"
						class:selected={index === selected}
						role="option"
						aria-selected={index === selected}
						data-testid="palette-ask"
						onmousedown={(e) => {
							e.preventDefault();
							ask();
						}}
					>
						<span class="icon">✦</span>
						<span class="title">Ask AI “{query.trim()}”</span>
					</button>
				{/if}
			{/each}
			{#if asking}
				<p class="none" data-testid="palette-asking">Asking…</p>
			{/if}
			{#if answer !== null}
				<div class="answer" data-testid="palette-answer">{answer}</div>
			{/if}
			{#if items.length === 0}
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
	.content .body {
		display: flex;
		flex-direction: column;
		min-width: 0;
		flex: 1;
	}
	.snippet {
		color: var(--tx3);
		font-size: 12px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.label {
		margin-left: auto;
		color: var(--tx3);
		font-size: 11px;
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}
	.create .title {
		color: var(--acc-strong);
	}
	.ask .title {
		color: var(--acc-strong);
	}
	.answer {
		margin: 8px 10px;
		padding: 10px 12px;
		border-radius: 8px;
		background: var(--accbg);
		color: var(--tx);
		font-size: 13px;
		white-space: pre-wrap;
	}
	.none {
		margin: 10px;
		color: var(--tx3);
		font-size: 13px;
	}
</style>
