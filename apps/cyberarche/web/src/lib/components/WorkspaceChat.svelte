<script lang="ts">
	import { goto } from '$app/navigation';
	import {
		createWorkspaceChat,
		workspaceChatOpen,
		type WorkspaceChatVM
	} from '$lib/viewmodels/workspaceChat.svelte';

	let { workspaceId }: { workspaceId: string } = $props();

	let chat = $state<WorkspaceChatVM | null>(null);
	let draft = $state('');

	$effect(() => {
		chat = createWorkspaceChat(workspaceId);
	});

	function onKeydown(event: KeyboardEvent) {
		if (event.key === 'Escape') workspaceChatOpen.close();
	}

	async function send(event: SubmitEvent) {
		event.preventDefault();
		const text = draft.trim();
		if (!text || !chat) return;
		draft = '';
		await chat.send(text);
	}

	function openSource(id: string) {
		workspaceChatOpen.close();
		goto(`/w/${workspaceId}/d/${id}`);
	}
</script>

<svelte:window onkeydown={onKeydown} />

<!-- Backdrop: click to dismiss. -->
<div
	class="backdrop"
	role="button"
	tabindex="-1"
	aria-label="Close workspace chat"
	data-testid="workspace-chat-backdrop"
	onclick={() => workspaceChatOpen.close()}
	onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && workspaceChatOpen.close()}
></div>

<div
	class="panel"
	role="dialog"
	aria-modal="true"
	tabindex="-1"
	aria-label="Chat with workspace"
	data-testid="workspace-chat"
>
	<header class="head">
		<div>
			<h1>Chat with workspace</h1>
			<p class="sub">Ask across every document. Read-only — it never edits.</p>
		</div>
		<button
			class="close"
			aria-label="Close workspace chat"
			data-testid="workspace-chat-close"
			onclick={() => workspaceChatOpen.close()}>×</button
		>
	</header>

	<div class="thread" data-testid="workspace-chat-thread">
		{#if chat}
			{#each chat.messages as message, i (i)}
				<div class="bubble {message.role}" data-testid="chat-message-{message.role}">
					<p class="text">{message.content}</p>
					{#if message.sources && message.sources.length > 0}
						<div class="sources">
							{#each message.sources as source (source.id)}
								<button
									class="source-chip"
									data-testid="chat-source"
									onclick={() => openSource(source.id)}
									title="Open “{source.title}”">{source.title}</button
								>
							{/each}
						</div>
					{/if}
				</div>
			{:else}
				<p class="empty">Ask a question about anything in this workspace.</p>
			{/each}
			{#if chat.busy}
				<p class="thinking" data-testid="chat-busy">Thinking…</p>
			{/if}
			{#if chat.error}
				<p class="error" role="alert" data-testid="chat-error">{chat.error}</p>
			{/if}
		{/if}
	</div>

	<form class="composer" onsubmit={send}>
		<textarea
			rows="2"
			placeholder="Ask the workspace…"
			bind:value={draft}
			data-testid="chat-input"
			onkeydown={(e) => {
				if (e.key === 'Enter' && !e.shiftKey) {
					e.preventDefault();
					send(new SubmitEvent('submit'));
				}
			}}
		></textarea>
		<button
			class="btn btn-primary"
			type="submit"
			disabled={chat?.busy || !draft.trim()}
			data-testid="chat-send">Send</button
		>
	</form>
</div>

<style>
	.backdrop {
		position: fixed;
		inset: 0;
		z-index: 900;
		background: rgba(15, 15, 20, 0.35);
		backdrop-filter: blur(6px);
		-webkit-backdrop-filter: blur(6px);
		animation: fade 0.14s ease;
	}
	.panel {
		position: fixed;
		z-index: 901;
		top: 0;
		right: 0;
		height: 100vh;
		width: min(440px, 94vw);
		display: flex;
		flex-direction: column;
		background: var(--bg1);
		border-left: 1px solid var(--line);
		box-shadow: -8px 0 32px rgba(0, 0, 0, 0.2);
		animation: slide 0.16s cubic-bezier(0.2, 0.8, 0.3, 1);
	}
	@keyframes fade {
		from {
			opacity: 0;
		}
	}
	@keyframes slide {
		from {
			transform: translateX(24px);
			opacity: 0;
		}
	}
	.head {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 12px;
		padding: 18px 20px 12px;
		border-bottom: 1px solid var(--line);
	}
	.head h1 {
		margin: 0;
		font-size: 16px;
	}
	.sub {
		margin: 4px 0 0;
		font-size: 12px;
		color: var(--tx3);
	}
	.close {
		width: 28px;
		height: 28px;
		border: none;
		background: none;
		font-size: 22px;
		line-height: 1;
		color: var(--tx3);
		cursor: pointer;
		border-radius: var(--r-control);
	}
	.close:hover {
		background: var(--bg2);
		color: var(--tx);
	}
	.thread {
		flex: 1;
		min-height: 0;
		overflow-y: auto;
		padding: 16px 20px;
		display: flex;
		flex-direction: column;
		gap: 12px;
	}
	.bubble {
		max-width: 92%;
		padding: 9px 12px;
		border-radius: 12px;
		font-size: 14px;
		line-height: 1.5;
	}
	.bubble.user {
		align-self: flex-end;
		background: var(--accbg);
		color: var(--acc-strong);
	}
	.bubble.assistant {
		align-self: flex-start;
		background: var(--bg0);
		border: 1px solid var(--line);
	}
	.text {
		margin: 0;
		white-space: pre-wrap;
	}
	.sources {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
		margin-top: 8px;
	}
	.source-chip {
		font-size: 11.5px;
		padding: 3px 8px;
		border-radius: 999px;
		background: var(--bg2);
		color: var(--acc-strong);
		border: 1px solid var(--line);
		cursor: pointer;
		max-width: 100%;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.source-chip:hover {
		background: var(--accbg);
	}
	.empty,
	.thinking {
		color: var(--tx3);
		font-size: 13px;
	}
	.error {
		color: var(--rose);
		font-size: 13px;
	}
	.composer {
		display: flex;
		gap: 8px;
		align-items: flex-end;
		padding: 12px 20px 16px;
		border-top: 1px solid var(--line);
	}
	.composer textarea {
		flex: 1;
		resize: none;
		padding: 8px 10px;
		border: 1px solid var(--line);
		border-radius: var(--r-control);
		background: var(--bg0);
		color: var(--tx);
		font: inherit;
	}
	.btn.btn-primary:disabled {
		opacity: 0.5;
	}
</style>
