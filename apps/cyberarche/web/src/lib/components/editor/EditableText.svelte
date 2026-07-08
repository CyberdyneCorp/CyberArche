<script lang="ts">
	/** Caret-safe contenteditable: local DOM wins while focused; remote
	 * values are applied only when unfocused (block-level LWW, see D-9). */

	let {
		value = '',
		placeholder = '',
		focused = false,
		menuOpen = false,
		onchange,
		onenter,
		onbackspaceempty,
		onfocus,
		tag = 'div'
	}: {
		value?: string;
		placeholder?: string;
		focused?: boolean;
		/** While a menu (slash) owns navigation keys, yield them. */
		menuOpen?: boolean;
		onchange: (text: string) => void;
		onenter?: (before: string, after: string) => void;
		onbackspaceempty?: () => void;
		onfocus?: () => void;
		tag?: string;
	} = $props();

	let element = $state<HTMLElement | null>(null);

	$effect(() => {
		if (!element) return;
		if (document.activeElement !== element && element.textContent !== value) {
			element.textContent = value;
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

	function handleKeydown(event: KeyboardEvent) {
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
		}
	}
</script>

<svelte:element
	this={tag}
	bind:this={element}
	class="editable"
	contenteditable="true"
	role="textbox"
	tabindex="0"
	data-placeholder={placeholder}
	oninput={() => onchange(element?.textContent ?? '')}
	onkeydown={handleKeydown}
	onfocus={() => onfocus?.()}
></svelte:element>

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
</style>
