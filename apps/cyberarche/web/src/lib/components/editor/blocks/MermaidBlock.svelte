<script lang="ts">
	import mermaid from 'mermaid';

	import type { BlockComponentProps } from '$lib/editor/registry';
	import type { EditorVM } from '$lib/viewmodels/editor.svelte';

	let { block, editor }: BlockComponentProps = $props();
	const vm = editor as EditorVM;

	const source = $derived((block.data.source as string) ?? '');
	// Stable per instance: the block id never changes, and reading it INSIDE the
	// render effect would subscribe the effect to the whole `block` prop — which
	// gets a fresh object on every document mirror (i.e. every keystroke in any
	// block), re-rendering the diagram and causing the flicker/empty jitter.
	const renderId = $derived(`m-${block.id}`);
	let view = $state<'rendered' | 'source'>('rendered');
	let svg = $state('');
	let error = $state<string | null>(null);

	mermaid.initialize({ startOnLoad: false, theme: 'neutral' });

	// Depend ONLY on `source` (a value-memoized derived): the diagram re-renders
	// when its own source changes, never because another block was edited.
	$effect(() => {
		const current = source;
		if (!current.trim()) {
			svg = '';
			error = null;
			return;
		}
		let stale = false;
		mermaid
			.render(renderId, current)
			.then((result) => {
				if (stale) return; // a newer source arrived; drop this result
				svg = result.svg;
				error = null;
			})
			.catch((err: Error) => {
				if (!stale) error = err.message.split('\n')[0];
			});
		return () => {
			stale = true;
		};
	});
</script>

<div class="mermaid-block" data-testid="mermaid-block">
	<header>
		<span class="tag">mermaid</span>
		<div class="toggle" role="tablist">
			<button
				role="tab"
				aria-selected={view === 'rendered'}
				class:active={view === 'rendered'}
				onclick={() => (view = 'rendered')}>Rendered</button
			>
			<button
				role="tab"
				aria-selected={view === 'source'}
				class:active={view === 'source'}
				onclick={() => (view = 'source')}>Source</button
			>
		</div>
	</header>

	{#if view === 'source' || !source.trim()}
		<textarea
			class="source"
			value={source}
			placeholder={'flowchart LR\n  Query --> Embed --> Rerank'}
			oninput={(event) =>
				vm.updateData(block.id, { source: (event.target as HTMLTextAreaElement).value })}
			onfocus={() => vm.focus(block.id)}
		></textarea>
	{/if}
	{#if error}
		<p class="error" data-testid="mermaid-error">{error}</p>
	{:else if view === 'rendered' && svg}
		<div class="render" data-testid="mermaid-render">{@html svg}</div>
	{/if}
</div>

<style>
	.mermaid-block {
		background: var(--bg2);
		border-radius: var(--r-block);
		overflow: hidden;
	}
	header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 6px 10px;
		border-bottom: 1px solid var(--line);
	}
	.tag {
		font-family: var(--font-mono);
		font-size: 11px;
		color: var(--tx3);
	}
	.toggle {
		display: flex;
		background: var(--bg1);
		border-radius: var(--r-pill);
		padding: 2px;
	}
	.toggle button {
		padding: 2px 10px;
		border-radius: var(--r-pill);
		font-size: 11px;
		color: var(--tx2);
	}
	.toggle button.active {
		background: var(--bg3);
		color: var(--tx);
		font-weight: 500;
	}
	.source {
		width: 100%;
		border: none;
		outline: none;
		background: var(--bg1);
		font-family: var(--font-mono);
		font-size: 12.5px;
		padding: 12px 14px;
		min-height: 96px;
		resize: vertical;
	}
	.render {
		display: flex;
		justify-content: center;
		padding: 16px;
		background: var(--bg1);
	}
	.render :global(svg) {
		max-width: 100%;
	}
	.error {
		margin: 0;
		padding: 10px 14px;
		color: var(--rose);
		font-family: var(--font-mono);
		font-size: 12px;
	}
</style>
