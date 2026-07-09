/** Toast notifications: transient success/error/info messages shown top-right.
 * A module-level singleton, mounted once by <Toasts /> in the root layout. */

export type ToastKind = 'success' | 'error' | 'info';

export interface Toast {
	id: number;
	message: string;
	kind: ToastKind;
}

export function createToasts() {
	let items = $state<Toast[]>([]);
	let seq = 0;

	function push(message: string, kind: ToastKind = 'info', ttlMs = 4000): number {
		const id = ++seq;
		items = [...items, { id, message, kind }];
		if (ttlMs > 0) setTimeout(() => dismiss(id), ttlMs);
		return id;
	}

	function dismiss(id: number) {
		items = items.filter((t) => t.id !== id);
	}

	return {
		get items() {
			return items;
		},
		push,
		success: (message: string) => push(message, 'success'),
		error: (message: string) => push(message, 'error'),
		info: (message: string) => push(message, 'info'),
		dismiss
	};
}

export const toasts = createToasts();
