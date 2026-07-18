<script lang="ts">
	/** Caret-safe contenteditable: local DOM wins while focused; remote
	 * values are applied only when unfocused (block-level LWW, see D-9). */

	import { renderInline } from '$lib/editor/inline';
	import { linkIndex } from '$lib/viewmodels/link-index.svelte';

	let {
		value = '',
		placeholder = '',
		focused = false,
		menuOpen = false,
		rich = false,
		syncSignal = 0,
		ghost = '',
		onchange,
		onenter,
		onbackspaceempty,
		onmergeback,
		onfocus,
		oncontinue,
		onaccept,
		ondismiss,
		tag = 'div'
	}: {
		value?: string;
		placeholder?: string;
		focused?: boolean;
		/** While a menu (slash) owns navigation keys, yield them. */
		menuOpen?: boolean;
		/** Render inline math/emphasis when unfocused (display only). */
		rich?: boolean;
		/** Changes on undo/redo: forces a DOM re-sync from `value` even while the
		 * field is focused (normal remote edits stay caret-safe and don't set it). */
		syncSignal?: number;
		/** Dimmed "continue writing" suggestion shown inline after the caret when
		 * the caret is at the end of the block (empty = none). */
		ghost?: string;
		onchange: (text: string) => void;
		onenter?: (before: string, after: string) => void;
		onbackspaceempty?: () => void;
		/** Backspace at the very start of non-empty text: merge into previous. */
		onmergeback?: () => void;
		onfocus?: () => void;
		/** Typing paused with the caret at the block end: request a continuation. */
		oncontinue?: (text: string) => void;
		/** Tab pressed while a ghost suggestion is shown: accept it. */
		onaccept?: () => void;
		/** Drop the current ghost suggestion (Escape, edit, navigation, blur). */
		ondismiss?: () => void;
		tag?: string;
	} = $props();

	// Modifier keys that must not dismiss the ghost (e.g. Shift to start a
	// selection, Cmd/Ctrl for shortcuts). Any other key edits or moves the caret.
	const GHOST_HOLD_KEYS = new Set(['Shift', 'Control', 'Alt', 'Meta']);

	let element = $state<HTMLElement | null>(null);

	// True between focus and blur. Drives the raw/rendered swap for `rich`
	// fields, so a cell re-renders on blur even though the block-level `focused`
	// prop doesn't flip per cell.
	let editing = $state(false);

	// Editing shows raw source (so the caret and typing work); when not editing
	// and `rich`, we render inline math/emphasis. Never touch content while the
	// element is the active input, or we'd drop the caret.
	$effect(() => {
		// Read every reactive dep up front: if we returned early at the guard
		// below before reading them, Svelte would not subscribe, and a later
		// blur (editing -> false) would never re-run this effect to render.
		const current = value;
		const isEditing = editing;
		const isRich = rich;
		if (!element || document.activeElement === element) return;
		if (isEditing) {
			if (element.textContent !== current) element.textContent = current;
		} else if (isRich) {
			element.innerHTML = renderInline(current, linkIndex.hrefFor);
		} else if (element.textContent !== current) {
			element.textContent = current;
		}
	});

	// Undo/redo: the sync effect above bails while the element is focused (to keep
	// the caret during typing), so a local undo would be invisible. When
	// `syncSignal` changes we force the DOM to match the model and drop the caret
	// at the end. Guarded so ordinary typing (which doesn't bump the signal) is
	// untouched.
	let lastSyncSignal = -1; // sentinel: any real signal (>= 0) differs on mount
	$effect(() => {
		const signal = syncSignal;
		const current = value;
		if (!element || signal === lastSyncSignal) return;
		lastSyncSignal = signal;
		if (!editing && rich) {
			element.innerHTML = renderInline(current, linkIndex.hrefFor);
			return;
		}
		if (element.textContent === current) return;
		element.textContent = current;
		if (document.activeElement === element) {
			const range = document.createRange();
			range.selectNodeContents(element);
			range.collapse(false);
			const selection = window.getSelection();
			selection?.removeAllRanges();
			selection?.addRange(range);
		}
	});

	$effect(() => {
		if (focused && element && document.activeElement !== element) {
			element.focus();
			// Caret to end.
			const range = document.createRange();
			range.selectNodeContents(element);
			range.collapse(false);
			const selection = window.getSelection();
			selection?.removeAllRanges();
			selection?.addRange(range);
		}
	});

	function caretOffset(): number {
		const selection = window.getSelection();
		if (!selection?.anchorNode || !element?.contains(selection.anchorNode)) {
			return (element?.textContent ?? '').length;
		}
		return selection.anchorOffset;
	}

	function caretAtEnd(): boolean {
		const selection = window.getSelection();
		return (
			(selection?.isCollapsed ?? true) &&
			caretOffset() === (element?.textContent ?? '').length
		);
	}

	// "Continue writing": Tab accepts a shown ghost, Escape/any edit/navigation
	// key drops it. Returns true when the key was fully handled here.
	function handleGhostKey(event: KeyboardEvent): boolean {
		if (!ghost) return false;
		if (event.key === 'Tab') {
			event.preventDefault();
			onaccept?.();
			return true;
		}
		if (event.key === 'Escape') {
			event.preventDefault();
			ondismiss?.();
			return true;
		}
		if (!GHOST_HOLD_KEYS.has(event.key)) ondismiss?.();
		return false;
	}

	// After typing, if the caret rests at the block end, ask for a continuation.
	function maybeContinue(text: string): void {
		if (oncontinue && !menuOpen && caretAtEnd()) oncontinue(text);
	}

	function handleKeydown(event: KeyboardEvent) {
		if (handleGhostKey(event)) return;
		if (menuOpen && ['Enter', 'ArrowUp', 'ArrowDown', 'Escape'].includes(event.key)) {
			event.preventDefault(); // the menu's window listener handles these
			return;
		}
		const text = element?.textContent ?? '';
		if (event.key === 'Enter' && !event.shiftKey && onenter) {
			event.preventDefault();
			const offset = caretOffset();
			onenter(text.slice(0, offset), text.slice(offset));
		}
		if (event.key === 'Backspace' && text === '' && onbackspaceempty) {
			event.preventDefault();
			onbackspaceempty();
		} else if (
			event.key === 'Backspace' &&
			text !== '' &&
			caretOffset() === 0 &&
			window.getSelection()?.isCollapsed &&
			onmergeback
		) {
			// At the start of non-empty text: merge into the previous block.
			event.preventDefault();
			onmergeback();
		}
	}
</script>

<svelte:element
	this={tag}
	bind:this={element}
	class="editable"
	class:has-ghost={!!ghost}
	contenteditable="true"
	role="textbox"
	tabindex="0"
	data-placeholder={placeholder}
	oninput={() => {
		const text = element?.textContent ?? '';
		onchange(text);
		maybeContinue(text);
	}}
	onkeydown={handleKeydown}
	onfocus={() => {
		editing = true;
		// Native focus can precede the reactive `focused` prop; restore raw
		// source immediately so a rich field is edited as source, not its
		// rendered HTML.
		if (rich && element && element.textContent !== value) {
			element.textContent = value;
		}
		onfocus?.();
	}}
	onblur={() => {
		editing = false;
		ondismiss?.(); // leaving the field drops any pending ghost suggestion
	}}
></svelte:element>{#if ghost}<span
		class="ghost-suggestion"
		contenteditable="false"
		aria-hidden="true"
		data-testid="ghost-suggestion">{ghost}</span
	>{/if}

<style>
	.editable {
		outline: none;
		min-height: 1.4em;
		white-space: pre-wrap;
		word-break: break-word;
	}
	.editable:empty::before {
		content: attr(data-placeholder);
		color: var(--tx3);
		pointer-events: none;
	}
	/* While a ghost suggestion is shown, the field flows inline so the dimmed
	 * continuation reads as the next words right after the caret. */
	.editable.has-ghost {
		display: inline;
	}
	.ghost-suggestion {
		color: var(--tx3);
		opacity: 0.7;
		pointer-events: none;
		user-select: none;
		white-space: pre-wrap;
	}
</style>
