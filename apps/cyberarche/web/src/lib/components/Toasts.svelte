<script lang="ts">
	import { toasts } from '$lib/viewmodels/toasts.svelte';
</script>

<div class="toasts" data-testid="toasts">
	{#each toasts.items as t (t.id)}
		<div class="toast {t.kind}" role="status" data-testid="toast">
			<span class="msg">{t.message}</span>
			<button class="close" aria-label="Dismiss" onclick={() => toasts.dismiss(t.id)}>✕</button>
		</div>
	{/each}
</div>

<style>
	.toasts {
		position: fixed;
		top: 16px;
		right: 16px;
		z-index: 2000;
		display: flex;
		flex-direction: column;
		gap: 8px;
		max-width: min(360px, calc(100vw - 32px));
	}
	.toast {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 10px 12px;
		border-radius: 10px;
		background: var(--bg1, #fff);
		color: var(--tx, #111);
		border: 1px solid var(--line, #e5e7eb);
		border-left: 3px solid var(--tx3, #9ca3af);
		box-shadow: 0 6px 20px rgba(0, 0, 0, 0.16);
		font-size: 13px;
		animation: toast-in 0.16s ease-out;
	}
	.toast.success {
		border-left-color: var(--green, #16a34a);
	}
	.toast.error {
		border-left-color: var(--rose, #e11d48);
	}
	.toast.info {
		border-left-color: var(--acc, #4f46e5);
	}
	.msg {
		flex: 1;
		min-width: 0;
	}
	.close {
		color: var(--tx3, #9ca3af);
		font-size: 11px;
		padding: 2px 4px;
		border-radius: 4px;
	}
	.close:hover {
		color: var(--tx, #111);
		background: var(--bg2, #f3f4f6);
	}
	@keyframes toast-in {
		from {
			opacity: 0;
			transform: translateY(-6px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}
</style>
