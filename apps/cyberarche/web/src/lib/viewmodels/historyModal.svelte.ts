/** Open/close state for the History modal — a module singleton so a button in
 * the document header can open the modal the document page renders. */
export function createHistoryModal() {
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

export const historyModal = createHistoryModal();
