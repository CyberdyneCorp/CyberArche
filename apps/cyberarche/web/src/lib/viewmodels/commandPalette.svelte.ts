/** Open/close state for the ⌘K command palette — a module singleton so both the
 * keyboard shortcut (workspace layout) and the sidebar Search button open the
 * same palette. */
export function createCommandPalette() {
	let open = $state(false);
	return {
		get isOpen() {
			return open;
		},
		open() {
			open = true;
		},
		close() {
			open = false;
		},
		toggle() {
			open = !open;
		}
	};
}

export const commandPalette = createCommandPalette();
