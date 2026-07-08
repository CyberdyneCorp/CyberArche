<script lang="ts">
	import katex from 'katex';
	import 'katex/dist/katex.min.css';

	import type { BlockComponentProps } from '$lib/editor/registry';
	import type { EditorVM } from '$lib/viewmodels/editor.svelte';

	let { block, editor }: BlockComponentProps = $props();
	const vm = editor as EditorVM;

	const source = $derived((block.data.source as string) ?? '');
	let editing = $state(false);

	const rendered = $derived.by(() => {
		if (!source) return { html: '', error: null as string | null };
		try {
			return {
				html: katex.renderToString(source, { displayMode: true, throwOnError: true }),
				error: null
			};
		} catch (error) {
			return { html: '', error: (error as Error).message };
		}
	});
</script>

<div class="latex-block" data-testid="latex-block">
	{#if editing || !source}
		<textarea
			class="source"
			value={source}
			placeholder={'\\sum_{i=1}^{n} x_i^2'}
			oninput={(event) =>
				vm.updateData(block.id, { source: (event.target as HTMLTextAreaElement).value })}
			onblur={() => (editing = false)}
			onfocus={() => vm.focus(block.id)}
		></textarea>
	{/if}
	{#if rendered.error}
		<p class="error" data-testid="latex-error">LaTeX error: {rendered.error}</p>
	{:else if rendered.html}
		<div
			class="render"
			role="button"
			tabindex="0"
			onclick={() => (editing = true)}
			onkeydown={(event) => event.key === 'Enter' && (editing = true)}
		>
			{@html rendered.html}
		</div>
	{/if}
</div>

<style>
	.latex-block {
		padding: 6px 0;
	}
	.source {
		width: 100%;
		font-family: var(--font-mono);
		font-size: 12.5px;
		border: 1px solid var(--line2);
		border-radius: var(--r-control);
		background: var(--bg2);
		padding: 8px 10px;
		resize: vertical;
		outline: none;
	}
	.render {
		text-align: center;
		padding: 8px;
		cursor: text;
		font-family: var(--font-math);
	}
	.error {
		margin: 4px 0 0;
		color: var(--rose);
		font-size: 12px;
		font-family: var(--font-mono);
	}
</style>
