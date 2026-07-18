/** DOM Selection helpers for the inline "Ask AI" bubble (inline-ai-selection).
 * Kept out of the component so the offset math stays testable and the view
 * stays simple. */

/** A non-empty text selection wholly inside one editable block. */
export interface RawBlockSelection {
	blockId: string;
	start: number;
	end: number;
	/** The editable's current text — equals the stored markdown source only
	 * while the field is in raw-editing mode (the caller must check). */
	text: string;
	/** Bounding rect of the selection, in viewport coordinates. */
	rect: DOMRect;
}

/** Absolute character offset of (node, off) within `el`'s text content. */
function absoluteOffset(el: HTMLElement, node: Node, off: number): number {
	const range = document.createRange();
	range.selectNodeContents(el);
	range.setEnd(node, off);
	return range.toString().length;
}

function closestEditable(node: Node | null): HTMLElement | null {
	const el = node instanceof HTMLElement ? node : (node?.parentElement ?? null);
	return el?.closest<HTMLElement>('.editable') ?? null;
}

/**
 * The current selection if it is a non-empty range wholly inside a single
 * editable block. Collapsed carets and selections that span multiple blocks
 * return null — the inline transform applies to one block's text only.
 */
export function readBlockSelection(): RawBlockSelection | null {
	const selection = window.getSelection();
	if (!selection || selection.isCollapsed || selection.rangeCount === 0) return null;
	const range = selection.getRangeAt(0);
	const editable = closestEditable(range.startContainer);
	// Single-block only: both ends of the selection must sit in the same editable.
	if (!editable || closestEditable(range.endContainer) !== editable) return null;
	const blockId = editable.closest<HTMLElement>('[data-block-id]')?.dataset.blockId;
	if (!blockId) return null;
	const a = absoluteOffset(editable, range.startContainer, range.startOffset);
	const b = absoluteOffset(editable, range.endContainer, range.endOffset);
	const start = Math.min(a, b);
	const end = Math.max(a, b);
	if (start === end) return null;
	return { blockId, start, end, text: editable.textContent ?? '', rect: range.getBoundingClientRect() };
}
