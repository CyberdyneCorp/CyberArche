<script lang="ts">
	/** Renders an image served behind bearer auth (our /api/v1/.../files/...):
	 * an <img> tag can't send the Authorization header, so we fetch the bytes
	 * with the token and show them via an object URL, revoked on teardown. */
	import { getBlob } from '$lib/api/http';

	let { src, alt = '' }: { src: string; alt?: string } = $props();

	let objectUrl = $state<string | null>(null);
	let failed = $state(false);

	$effect(() => {
		const path = src;
		failed = false;
		objectUrl = null;
		let created: string | null = null;
		let cancelled = false;
		getBlob(path)
			.then((blob) => {
				if (cancelled) return;
				created = URL.createObjectURL(blob);
				objectUrl = created;
			})
			.catch(() => {
				if (!cancelled) failed = true;
			});
		return () => {
			cancelled = true;
			if (created) URL.revokeObjectURL(created);
		};
	});
</script>

{#if failed}
	<div class="state" data-testid="image-error">Couldn't load image</div>
{:else if objectUrl}
	<img src={objectUrl} {alt} data-testid="auth-image" />
{:else}
	<div class="state">Loading…</div>
{/if}

<style>
	img {
		max-width: 100%;
		border-radius: var(--r-block, 8px);
		display: block;
	}
	.state {
		color: var(--tx3);
		font-size: 13px;
		padding: 12px;
	}
</style>
