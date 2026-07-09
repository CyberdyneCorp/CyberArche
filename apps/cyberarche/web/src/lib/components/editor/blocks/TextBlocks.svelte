<script lang="ts" module>
	// Text-family blocks share one component: paragraph, heading, lists,
	// todo, callout, quote. The registry maps each type here with its own
	// create()/markdownPrefix; rendering varies by block.type.
</script>

<script lang="ts">
	import type { BlockComponentProps } from '$lib/editor/registry';
	import type { EditorVM } from '$lib/viewmodels/editor.svelte';
	import EditableText from '../EditableText.svelte';

	let { block, editor }: BlockComponentProps = $props();
	const vm = editor as EditorVM;

	const text = $derived((block.data.text as string) ?? '');
	const level = $derived((block.data.level as number) ?? 1);
	const checked = $derived(Boolean(block.data.checked));
	const focused = $derived(vm.focusedId === block.id);

	function onchange(next: string) {
		vm.handleTextInput(block.id, next);
	}
	function onenter(before: string, after: string) {
		vm.updateData(block.id, { text: before });
		const id = vm.insertAfter(block.id, listLike() ? block.type : 'paragraph');
		if (after) vm.updateData(id, { text: after });
	}
	function onbackspaceempty() {
		if (block.type !== 'paragraph') {
			vm.transform(block.id, 'paragraph', { text: '' });
		} else {
			vm.remove(block.id);
		}
	}
	function onmergeback() {
		// Backspace at the start of non-empty text: join into the previous block.
		vm.mergeWithPrevious(block.id);
	}
	function listLike() {
		return ['bulleted_list', 'numbered_list', 'todo'].includes(block.type);
	}
	const shared = $derived({
		value: text,
		focused,
		rich: true, // render inline math ($…$) and emphasis when unfocused
		menuOpen: vm.slashFor === block.id,
		onchange,
		onenter,
		onbackspaceempty,
		onmergeback,
		onfocus: () => vm.focus(block.id)
	});
</script>

{#if block.type === 'heading'}
	<div class="heading" data-level={Math.min(level, 3)}>
		<EditableText {...shared} placeholder="Heading" />
	</div>
{:else if block.type === 'bulleted_list' || block.type === 'numbered_list'}
	<div class="list-item">
		<span class="marker">{block.type === 'bulleted_list' ? '•' : '1.'}</span>
		<EditableText {...shared} placeholder="List item" />
	</div>
{:else if block.type === 'todo'}
	<div class="list-item">
		<input
			type="checkbox"
			{checked}
			onchange={(event) =>
				vm.updateData(block.id, { checked: (event.target as HTMLInputElement).checked })}
		/>
		<span class:done={checked}>
			<EditableText {...shared} placeholder="To-do" />
		</span>
	</div>
{:else if block.type === 'callout'}
	<div class="callout">
		<span class="callout-icon">◆</span>
		<EditableText {...shared} placeholder="Callout" />
	</div>
{:else if block.type === 'quote'}
	<blockquote class="quote">
		<EditableText {...shared} placeholder="Quote" />
	</blockquote>
{:else}
	<div class="paragraph">
		<EditableText {...shared} placeholder="Type '/' for blocks" />
	</div>
{/if}

<style>
	.paragraph,
	.list-item,
	.quote,
	.callout {
		font-size: 15.5px;
		line-height: 1.7;
	}
	.heading[data-level='1'] :global(.editable) {
		font-size: 26px;
		font-weight: 700;
		line-height: 1.3;
	}
	.heading[data-level='2'] :global(.editable) {
		font-size: 21px;
		font-weight: 600;
		line-height: 1.35;
	}
	.heading[data-level='3'] :global(.editable) {
		font-size: 16.5px;
		font-weight: 600;
	}
	.list-item {
		display: flex;
		gap: 8px;
		align-items: baseline;
	}
	.list-item :global(.editable) {
		flex: 1;
	}
	.marker {
		color: var(--tx2);
		user-select: none;
	}
	.done :global(.editable) {
		text-decoration: line-through;
		color: var(--tx3);
	}
	.callout {
		display: flex;
		gap: 10px;
		background: var(--accbg);
		border-radius: var(--r-block);
		padding: 12px 14px;
	}
	.callout :global(.editable) {
		flex: 1;
	}
	.callout-icon {
		color: var(--acc);
	}
	.quote {
		margin: 0;
		border-left: 3px solid var(--line2);
		padding-left: 14px;
		color: var(--tx2);
	}
</style>
