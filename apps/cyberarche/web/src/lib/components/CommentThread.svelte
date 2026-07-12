<script lang="ts">
	import type { SharingVM } from '$lib/viewmodels/sharing.svelte';
	import { getDocument } from '$lib/api/documents';
	import { teamspaceMembers, type TeamspaceMember } from '$lib/api/teamspaces';

	let {
		sharing,
		blockId,
		onclose
	}: { sharing: SharingVM; blockId: string; onclose: () => void } = $props();

	let draft = $state('');
	let inputEl = $state<HTMLInputElement | null>(null);

	const thread = $derived(sharing.commentsFor(blockId));

	// @mention autocomplete: members of the document's teamspace, fetched lazily.
	let members = $state<TeamspaceMember[] | null>(null);
	let mentionQuery = $state<string | null>(null);

	async function loadMembers(): Promise<void> {
		if (members !== null) return;
		members = [];
		try {
			const doc = await getDocument(sharing.documentId);
			if (doc.teamspace_id) members = await teamspaceMembers(doc.teamspace_id);
		} catch {
			/* private doc / no access — no suggestions */
		}
	}

	const suggestions = $derived(
		mentionQuery === null || !members
			? []
			: members
					.filter((m) => m.user_id.toLowerCase().includes(mentionQuery!.toLowerCase()))
					.slice(0, 6)
	);

	function onInput(): void {
		const value = inputEl?.value ?? '';
		const m = /@(\w*)$/.exec(value); // an @ token being typed at the caret
		mentionQuery = m ? m[1] : null;
		if (mentionQuery !== null) void loadMembers();
	}

	function pickMention(userId: string): void {
		draft = draft.replace(/@(\w*)$/, `@[${userId}] `);
		mentionQuery = null;
		inputEl?.focus();
	}

	/** Split a comment body into text and `@[id]` mention chips. */
	function segments(body: string): { text: string; mention?: string }[] {
		return body.split(/(@\[[^\]]+\])/g).map((part) => {
			const m = /^@\[([^\]]+)\]$/.exec(part);
			return m ? { text: '', mention: m[1] } : { text: part };
		});
	}

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		const body = draft.trim();
		if (!body) return;
		draft = '';
		mentionQuery = null;
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
			<p class="body">
				{#each segments(comment.body) as seg}
					{#if seg.mention}<span class="mention">@{seg.mention.slice(0, 8)}</span>{:else}{seg.text}{/if}
				{/each}
			</p>
		</div>
	{:else}
		<p class="empty">No open comments</p>
	{/each}
	<form onsubmit={submit}>
		<input
			bind:this={inputEl}
			class="input"
			placeholder="Add a comment… (@ to mention)"
			bind:value={draft}
			oninput={onInput}
			data-testid="comment-input"
		/>
		{#if suggestions.length}
			<div class="mentions" data-testid="mention-suggestions">
				{#each suggestions as m (m.user_id)}
					<button type="button" class="m-item" onclick={() => pickMention(m.user_id)}>
						@{m.user_id.slice(0, 12)}<span class="m-role">{m.role}</span>
					</button>
				{/each}
			</div>
		{/if}
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
		position: relative;
	}
	.input {
		width: 100%;
	}
	.mention {
		display: inline-block;
		padding: 0 4px;
		border-radius: 4px;
		background: var(--accbg2);
		color: var(--acc-strong);
		font-weight: 500;
	}
	.mentions {
		position: absolute;
		left: 0;
		right: 0;
		bottom: calc(100% + 4px);
		background: var(--bg1);
		border: 1px solid var(--line);
		border-radius: 8px;
		box-shadow: var(--sh3);
		overflow: hidden;
		z-index: 5;
	}
	.m-item {
		width: 100%;
		display: flex;
		justify-content: space-between;
		gap: 8px;
		padding: 6px 9px;
		text-align: left;
		font-size: 12px;
		color: var(--tx);
	}
	.m-item:hover {
		background: var(--bg2);
	}
	.m-role {
		color: var(--tx3);
		text-transform: capitalize;
	}
</style>
