/** Open/close state for the Settings modal — a module singleton so the sidebar
 * button (anywhere in the shell) can open the modal that the workspace layout
 * renders. */
export function createSettingsModal() {
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
		}
	};
}

export const settingsModal = createSettingsModal();
