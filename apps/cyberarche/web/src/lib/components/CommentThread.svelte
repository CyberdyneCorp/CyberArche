<script lang="ts">
	import type { SharingVM } from '$lib/viewmodels/sharing.svelte';

	let {
		sharing,
		blockId,
		onclose
	}: { sharing: SharingVM; blockId: string; onclose: () => void } = $props();

	let draft = $state('');

	const thread = $derived(sharing.commentsFor(blockId));

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		const body = draft.trim();
		if (!body) return;
		draft = '';
		await sharing.comment(blockId, body);
	}
</script>

<div class="thread" data-testid="comment-thread">
	<header>
		<strong>Comments</strong>
		<button class="close" aria-label="Close comments" onclick={onclose}>✕</button>
	</header>
	{#each thread as comment (comment.id)}
		<div class="comment" data-testid="comment">
			<div class="meta">
				<span class="author">{comment.author_id.slice(0, 8)}</span>
				<button
					class="resolve"
					data-testid="resolve-comment"
					onclick={() => sharing.resolve(comment.id)}>Resolve</button
				>
			</div>
			<p class="body">{comment.body}</p>
		</div>
	{:else}
		<p class="empty">No open comments</p>
	{/each}
	<form onsubmit={submit}>
		<input
			class="input"
			placeholder="Add a comment…"
			bind:value={draft}
			data-testid="comment-input"
		/>
	</form>
</div>

<style>
	.thread {
		position: absolute;
		right: -8px;
		top: 100%;
		z-index: 40;
		width: 260px;
		background: var(--bg1);
		border: 1px solid var(--line);
		border-radius: var(--r-block);
		box-shadow: var(--sh2);
		padding: 10px 12px;
	}
	header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 6px;
	}
	.close {
		color: var(--tx3);
	}
	.comment {
		border-top: 1px solid var(--line);
		padding: 6px 0;
	}
	.meta {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}
	.author {
		font-family: var(--font-mono);
		font-size: 10.5px;
		color: var(--tx3);
	}
	.resolve {
		font-size: 11px;
		color: var(--ok);
	}
	.body {
		margin: 3px 0 0;
	}
	.empty {
		color: var(--tx3);
	}
	form {
		margin-top: 8px;
	}
	.input {
		width: 100%;
	}
</style>
