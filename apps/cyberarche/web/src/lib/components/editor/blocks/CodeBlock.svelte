<script lang="ts">
	import hljs from 'highlight.js/lib/common';
	import 'highlight.js/styles/atom-one-light.css';

	import type { BlockComponentProps } from '$lib/editor/registry';
	import type { EditorVM } from '$lib/viewmodels/editor.svelte';

	let { block, editor }: BlockComponentProps = $props();
	const vm = editor as EditorVM;

	const source = $derived((block.data.source as string) ?? '');
	const language = $derived((block.data.language as string) ?? 'python');
	let editing = $state(false);

	const highlighted = $derived.by(() => {
		try {
			return hljs.getLanguage(language)
				? hljs.highlight(source, { language }).value
				: hljs.highlightAuto(source).value;
		} catch {
			return source;
		}
	});

	const LANGUAGES = ['python', 'typescript', 'javascript', 'go', 'rust', 'sql', 'bash', 'json', 'yaml', 'html', 'css', 'cpp', 'java'];
</script>

<div class="code-block" data-testid="code-block">
	<header>
		<select
			class="lang"
			value={language}
			onchange={(event) =>
				vm.updateData(block.id, { language: (event.target as HTMLSelectElement).value })}
		>
			{#each LANGUAGES as lang (lang)}
				<option value={lang}>{lang}</option>
			{/each}
		</select>
		<button class="copy" onclick={() => navigator.clipboard.writeText(source)}>Copy</button>
	</header>
	{#if editing}
		<textarea
			class="source"
			value={source}
			oninput={(event) =>
				vm.updateData(block.id, { source: (event.target as HTMLTextAreaElement).value })}
			onblur={() => (editing = false)}
			onfocus={() => vm.focus(block.id)}
		></textarea>
	{:else}
		<pre
			class="render"
			role="button"
			tabindex="0"
			onclick={() => (editing = true)}
			onkeydown={(event) => event.key === 'Enter' && (editing = true)}><code
				>{@html highlighted || '<span class="hint">Click to add code</span>'}</code
			></pre>
	{/if}
</div>

<style>
	.code-block {
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
	.lang {
		font-family: var(--font-mono);
		font-size: 11px;
		background: transparent;
		border: none;
		color: var(--tx2);
	}
	.copy {
		font-size: 11px;
		color: var(--tx3);
	}
	.copy:hover {
		color: var(--tx);
	}
	.render,
	.source {
		margin: 0;
		padding: 12px 14px;
		font-family: var(--font-mono);
		font-size: 12.5px;
		line-height: 1.6;
		min-height: 40px;
		white-space: pre-wrap;
		word-break: break-word;
	}
	.render {
		cursor: text;
	}
	.source {
		width: 100%;
		border: none;
		outline: none;
		background: var(--bg1);
		resize: vertical;
		min-height: 96px;
	}
	.hint {
		color: var(--tx3);
	}
</style>
