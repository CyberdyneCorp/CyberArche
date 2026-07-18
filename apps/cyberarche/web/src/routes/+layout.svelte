<script lang="ts">
	import '../app.css';
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { updated } from '$app/state';
	import { session } from '$lib/viewmodels/session.svelte';
	import Toasts from '$lib/components/Toasts.svelte';
	import ConfirmDialog from '$lib/components/ConfirmDialog.svelte';

	let { children } = $props();

	// Restore a session from the HttpOnly refresh cookie (async silent refresh).
	void session.init();

	// Register the service worker for the offline app shell. Idempotent with
	// push.ts's registration (same '/sw.js' URL + default scope → the browser
	// dedupes). Guarded for SSR and unsupported browsers; failures are ignored.
	onMount(() => {
		if (browser && 'serviceWorker' in navigator) {
			navigator.serviceWorker.register('/sw.js').catch(() => {});
		}
	});

	// A new build was deployed while this tab was open: its in-memory JS is now
	// stale (this is what left tabs on old realtime/reconnect logic). Offer a
	// reload rather than forcing one, so any unsynced offline edit isn't lost.
	function reload() {
		location.reload();
	}
</script>

{@render children()}

<Toasts />
<ConfirmDialog />

{#if updated.current}
	<button class="update-banner" data-testid="update-banner" onclick={reload}>
		A new version is available — click to reload
	</button>
{/if}

<style>
	.update-banner {
		position: fixed;
		left: 50%;
		bottom: 16px;
		transform: translateX(-50%);
		z-index: 1000;
		background: var(--acc, #4f46e5);
		color: #fff;
		border: none;
		border-radius: 999px;
		padding: 10px 18px;
		font-size: 13px;
		box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
		cursor: pointer;
	}
	.update-banner:hover {
		filter: brightness(1.08);
	}
</style>
