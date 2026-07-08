<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { documentTree } from '$lib/viewmodels/document-tree.svelte';

	async function newDocument() {
		const document = await documentTree.create('');
		await goto(`/w/${page.params.workspaceId}/d/${document.id}`);
	}
</script>

<div class="empty-state">
	<p>Select a document from the sidebar, or</p>
	<button class="btn btn-primary" onclick={newDocument}>＋ New document</button>
	<p class="hint">Type <kbd>/</kbd> in a document to insert blocks — text, code, LaTeX, Mermaid, tables, whiteboards.</p>
</div>

<style>
	.empty-state {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 12px;
		height: 100%;
		color: var(--tx2);
	}
	.hint {
		color: var(--tx3);
		font-size: 12px;
	}
	kbd {
		font-family: var(--font-mono);
		background: var(--bg2);
		border: 1px solid var(--line2);
		border-radius: 4px;
		padding: 1px 5px;
	}
</style>
