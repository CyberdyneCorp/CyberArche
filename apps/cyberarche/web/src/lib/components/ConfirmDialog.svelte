<script lang="ts">
	import { dialogs } from '$lib/viewmodels/dialogs.svelte';

	let value = $state('');

	// When a prompt opens, seed the input with its initial value.
	$effect(() => {
		const c = dialogs.current;
		if (c?.kind === 'prompt') value = c.initial;
	});

	function onkeydown(event: KeyboardEvent) {
		if (event.key === 'Escape') {
			event.preventDefault();
			dialogs.cancel();
		} else if (event.key === 'Enter' && dialogs.current?.kind === 'prompt') {
			event.preventDefault();
			dialogs.accept(value);
		}
	}
</script>

{#if dialogs.current}
	{@const c = dialogs.current}
	<div class="backdrop" role="presentation" onclick={() => dialogs.cancel()}>
		<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
		<div
			class="dialog"
			role="dialog"
			aria-modal="true"
			aria-label={c.title}
			data-testid="confirm-dialog"
			tabindex="-1"
			onclick={(e) => e.stopPropagation()}
			{onkeydown}
		>
			<h2>{c.title}</h2>
			{#if c.message}<p class="message">{c.message}</p>{/if}
			{#if c.kind === 'prompt'}
				<!-- svelte-ignore a11y_autofocus -->
				<input
					class="input"
					bind:value
					placeholder={c.placeholder}
					autofocus
					data-testid="dialog-input"
				/>
			{/if}
			<div class="actions">
				<button class="btn ghost" data-testid="dialog-cancel" onclick={() => dialogs.cancel()}>
					Cancel
				</button>
				{#if c.kind === 'confirm'}
					<button
						class="btn"
						class:danger={c.danger}
						data-testid="dialog-confirm"
						onclick={() => dialogs.accept()}>{c.confirmLabel}</button
					>
				{:else}
					<button class="btn" data-testid="dialog-confirm" onclick={() => dialogs.accept(value)}>
						{c.confirmLabel}
					</button>
				{/if}
			</div>
		</div>
	</div>
{/if}

<style>
	.backdrop {
		position: fixed;
		inset: 0;
		z-index: 1500;
		display: grid;
		place-items: center;
		background: rgba(0, 0, 0, 0.4);
		padding: 16px;
	}
	.dialog {
		width: min(400px, 100%);
		background: var(--bg1, #fff);
		color: var(--tx, #111);
		border: 1px solid var(--line, #e5e7eb);
		border-radius: 14px;
		padding: 20px;
		box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
	}
	.dialog h2 {
		margin: 0 0 8px;
		font-size: 15px;
		font-weight: 600;
	}
	.message {
		margin: 0 0 16px;
		font-size: 13px;
		color: var(--tx2, #4b5563);
		line-height: 1.5;
	}
	.input {
		width: 100%;
		margin-bottom: 16px;
		padding: 8px 10px;
		font-size: 13px;
		border: 1px solid var(--line, #e5e7eb);
		border-radius: 8px;
		background: var(--bg0, #fff);
		color: var(--tx, #111);
	}
	.actions {
		display: flex;
		justify-content: flex-end;
		gap: 8px;
	}
	.btn {
		padding: 7px 14px;
		border-radius: 8px;
		font-size: 13px;
		font-weight: 500;
		background: var(--acc, #4f46e5);
		color: #fff;
	}
	.btn:hover {
		filter: brightness(1.08);
	}
	.btn.ghost {
		background: transparent;
		color: var(--tx2, #4b5563);
	}
	.btn.ghost:hover {
		background: var(--bg2, #f3f4f6);
		filter: none;
	}
	.btn.danger {
		background: var(--rose, #e11d48);
	}
</style>
