<script lang="ts">
	/** Inline "Ask AI" bubble (inline-ai-selection spec): appears above a
	 * non-empty text selection inside one editable block and transforms the
	 * selected text in place via the LLM. Single-block selections only — a
	 * range spanning several blocks is ignored (its offsets can't map onto one
	 * block's stored source). The result is applied through the editor's normal
	 * text-update path, so it is undoable and syncs via the CRDT. */

	import type { EditorVM, SelectionTarget } from '$lib/viewmodels/editor.svelte';
	import { readBlockSelection } from '$lib/editor/selection';

	let { editor }: { editor: EditorVM } = $props();

	// The eligible selection and where to float the bubble (viewport coords).
	let target = $state<SelectionTarget | null>(null);
	let anchor = $state<{ top: number; left: number } | null>(null);
	// The Translate action swaps the menu for a small language picker.
	let picking = $state(false);

	const ACTIONS = [
		{ action: 'rewrite', label: 'Rewrite' },
		{ action: 'shorten', label: 'Shorten' },
		{ action: 'expand', label: 'Expand' },
		{ action: 'fix', label: 'Fix' }
	];
	const LANGUAGES = ['English', 'Español', 'Português', 'Français', 'Deutsch'];

	function dismiss() {
		target = null;
		anchor = null;
		picking = false;
	}

	/** Text-family blocks store their content as `data.text`; the selection
	 * offsets map onto it only while the editable shows raw source. */
	function sourceOf(blockId: string): string | null {
		const block = editor.blocks.find((b) => b.id === blockId);
		if (!block) return null;
		return String((block.data as { text?: string }).text ?? '');
	}

	// Recompute on every selection change. Keep the menu while a transform is in
	// flight or the language picker is open (the selection is preserved then).
	function onSelectionChange() {
		if (editor.selectionPending || picking) return;
		const found = readBlockSelection();
		if (!found || found.text !== sourceOf(found.blockId)) {
			dismiss();
			return;
		}
		target = { blockId: found.blockId, start: found.start, end: found.end };
		anchor = { top: found.rect.top, left: found.rect.left + found.rect.width / 2 };
	}

	async function run(action: string, langTarget?: string) {
		if (!target) return;
		await editor.transformSelection(target, action, langTarget);
		dismiss();
		window.getSelection()?.removeAllRanges();
	}

	function onKeydown(event: KeyboardEvent) {
		if (target && event.key === 'Escape') dismiss();
	}

	// An outside click dismisses; clicks on a menu button keep the selection
	// alive (the buttons preventDefault on mousedown) so `target` stays valid.
	function onOutside(event: MouseEvent) {
		if (target && !(event.target as HTMLElement).closest('.ai-bubble')) dismiss();
	}
</script>

<svelte:document onselectionchange={onSelectionChange} />
<svelte:window onkeydown={onKeydown} onmousedown={onOutside} />

{#if target && anchor && !editor.readOnly}
	<div
		class="ai-bubble"
		role="menu"
		data-testid="selection-menu"
		style:top="{anchor.top}px"
		style:left="{anchor.left}px"
	>
		{#if editor.selectionPending}
			<span class="pending" data-testid="selection-pending">Asking AI…</span>
		{:else if picking}
			{#each LANGUAGES as lang (lang)}
				<button
					role="menuitem"
					onmousedown={(event) => {
						event.preventDefault();
						run('translate', lang);
					}}>{lang}</button
				>
			{/each}
		{:else}
			<span class="tag">Ask AI</span>
			{#each ACTIONS as item (item.action)}
				<button
					role="menuitem"
					onmousedown={(event) => {
						event.preventDefault();
						run(item.action);
					}}>{item.label}</button
				>
			{/each}
			<button
				role="menuitem"
				onmousedown={(event) => {
					event.preventDefault();
					picking = true;
				}}>Translate ▾</button
			>
		{/if}
	</div>
{/if}

<style>
	.ai-bubble {
		position: fixed;
		z-index: 40;
		/* Centre horizontally over the selection and sit just above it. */
		transform: translate(-50%, calc(-100% - 8px));
		display: flex;
		align-items: center;
		gap: 2px;
		background: var(--bg1);
		border: 1px solid var(--line);
		border-radius: var(--r-control);
		box-shadow: var(--sh2);
		padding: 3px;
		animation: rise 120ms ease-out;
	}
	@keyframes rise {
		from {
			opacity: 0;
			transform: translate(-50%, calc(-100% - 4px));
		}
	}
	.tag {
		color: var(--acc);
		font-weight: 600;
		font-size: 11px;
		padding: 0 6px;
	}
	button {
		padding: 4px 8px;
		border-radius: var(--r-control);
		font-size: 13px;
		white-space: nowrap;
	}
	button:hover {
		background: var(--accbg);
	}
	.pending {
		color: var(--tx3);
		font-size: 13px;
		padding: 4px 10px;
	}
</style>
