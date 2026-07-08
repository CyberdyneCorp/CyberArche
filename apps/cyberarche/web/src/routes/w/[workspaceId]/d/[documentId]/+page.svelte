<script lang="ts">
	import { page } from '$app/state';
	import { getDocument, type Document } from '$lib/api/documents';
	import { documentTree } from '$lib/viewmodels/document-tree.svelte';

	const documentId = $derived(page.params.documentId!);

	let doc = $state<Document | null>(null);
	let titleDraft = $state('');

	$effect(() => {
		const id = documentId;
		doc = null;
		getDocument(id).then((loaded) => {
			doc = loaded;
			titleDraft = loaded.title === 'Untitled' ? '' : loaded.title;
		});
	});

	async function commitTitle() {
		if (!doc) return;
		const next = titleDraft.trim() || 'Untitled';
		if (next !== doc.title) {
			await documentTree.rename(doc.id, next);
			doc = { ...doc, title: next };
		}
	}
</script>

{#if doc}
	<article class="doc">
		<header class="topbar">
			<nav class="crumbs" aria-label="Breadcrumb">
				<span class="crumb">{doc.title}</span>
			</nav>
			<span class="chip chip-accent">Synced</span>
		</header>

		<div class="canvas">
			<input
				class="title"
				placeholder="Untitled"
				bind:value={titleDraft}
				onblur={commitTitle}
				onkeydown={(event) => event.key === 'Enter' && (event.target as HTMLInputElement).blur()}
				data-testid="doc-title"
			/>
			<div class="editor-placeholder" data-testid="editor">
				<p>The block editor lands here next — type <kbd>/</kbd> for blocks.</p>
			</div>
		</div>
	</article>
{:else}
	<div class="loading">Loading…</div>
{/if}

<style>
	.doc {
		display: flex;
		flex-direction: column;
		min-height: 100%;
	}
	.topbar {
		position: sticky;
		top: 0;
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 10px 20px;
		background: var(--bg1);
		border-bottom: 1px solid var(--line);
	}
	.crumbs {
		color: var(--tx2);
	}
	.canvas {
		width: min(760px, 92%);
		margin: 0 auto;
		padding: 48px 0 120px;
	}
	.title {
		width: 100%;
		border: none;
		outline: none;
		background: transparent;
		font-family: var(--font-ui);
		font-size: 34px;
		font-weight: 700;
		color: var(--tx);
		padding: 0;
	}
	.title::placeholder {
		color: var(--tx3);
	}
	.editor-placeholder {
		margin-top: 24px;
		color: var(--tx3);
		font-size: 15.5px;
		line-height: 1.7;
	}
	kbd {
		font-family: var(--font-mono);
		background: var(--bg2);
		border: 1px solid var(--line2);
		border-radius: 4px;
		padding: 1px 5px;
	}
	.loading {
		display: grid;
		place-items: center;
		height: 100%;
		color: var(--tx3);
	}
</style>
