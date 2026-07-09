<script lang="ts">
	import { parseEmbed } from '$lib/editor/embeds';
	import type { BlockComponentProps } from '$lib/editor/registry';
	import type { EditorVM } from '$lib/viewmodels/editor.svelte';

	let { block, editor }: BlockComponentProps = $props();
	// svelte-ignore state_referenced_locally
	const vm = editor as EditorVM; // the VM is a stable singleton for this block

	const url = $derived((block.data.url as string) ?? '');
	const embed = $derived(parseEmbed(url));

	let draft = $state('');

	function apply() {
		const next = draft.trim();
		if (next) vm.updateData(block.id, { url: next });
	}
</script>

<div class="embed-block" data-testid="embed-block" role="group" onfocusin={() => vm.focus(block.id)}>
	{#if url && embed}
		<div class="frame" data-provider={embed.provider}>
			<iframe
				src={embed.embedUrl}
				title="Embedded media"
				loading="lazy"
				allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
				allowfullscreen
				sandbox="allow-scripts allow-same-origin allow-popups allow-presentation"
				referrerpolicy="strict-origin-when-cross-origin"
				data-testid="embed-iframe"
			></iframe>
		</div>
		<div class="meta">
			<a href={url} target="_blank" rel="noopener noreferrer" data-testid="embed-open">Open link ↗</a>
			<button class="change" onclick={() => vm.updateData(block.id, { url: '' })}>Replace</button>
		</div>
	{:else}
		<div class="picker">
			<input
				class="url-input"
				placeholder="Paste a YouTube, Vimeo, or https link…"
				bind:value={draft}
				onkeydown={(e) => e.key === 'Enter' && apply()}
				data-testid="embed-url-input"
			/>
			<button class="btn" onclick={apply} data-testid="embed-url-apply">Embed</button>
			{#if url && !embed}
				<p class="err" data-testid="embed-invalid">That link can't be embedded (https only).</p>
			{/if}
		</div>
	{/if}
</div>

<style>
	.frame {
		position: relative;
		width: 100%;
		aspect-ratio: 16 / 9;
		background: #000;
		border-radius: var(--r-block, 8px);
		overflow: hidden;
	}
	.frame iframe {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
		border: 0;
	}
	.meta {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-top: 4px;
	}
	.meta a {
		font-size: 12px;
		color: var(--acc-strong, var(--acc));
		text-decoration: none;
	}
	.change {
		font-size: 11px;
		color: var(--tx3);
	}
	.change:hover {
		color: var(--tx);
	}
	.picker {
		display: flex;
		gap: 6px;
		flex-wrap: wrap;
		border: 1px dashed var(--line2, var(--line));
		border-radius: var(--r-block, 8px);
		padding: 14px;
		background: var(--bg1);
	}
	.url-input {
		flex: 1;
		min-width: 220px;
		padding: 7px 10px;
		border: 1px solid var(--line);
		border-radius: 8px;
		background: var(--bg0);
		color: var(--tx);
		font-size: 13px;
	}
	.btn {
		padding: 7px 12px;
		border-radius: 8px;
		background: var(--acc, #4f46e5);
		color: #fff;
		font-size: 13px;
	}
	.btn:hover {
		filter: brightness(1.08);
	}
	.err {
		flex-basis: 100%;
		margin: 0;
		color: var(--rose);
		font-size: 12px;
	}
</style>
