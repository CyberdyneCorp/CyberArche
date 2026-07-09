/** In-app confirm / prompt dialogs, promise-based, replacing the browser's
 * native confirm()/prompt(). A module-level singleton driven by <ConfirmDialog />
 * in the root layout: call `dialogs.confirm(...)` / `dialogs.prompt(...)` and
 * await the user's answer. */

interface ConfirmPending {
	kind: 'confirm';
	title: string;
	message: string;
	confirmLabel: string;
	danger: boolean;
	resolve: (ok: boolean) => void;
}

interface PromptPending {
	kind: 'prompt';
	title: string;
	message: string;
	placeholder: string;
	initial: string;
	confirmLabel: string;
	resolve: (value: string | null) => void;
}

type Pending = ConfirmPending | PromptPending;

export interface ConfirmOptions {
	title: string;
	message?: string;
	confirmLabel?: string;
	danger?: boolean;
}

export interface PromptOptions {
	title: string;
	message?: string;
	placeholder?: string;
	initial?: string;
	confirmLabel?: string;
}

export function createDialogs() {
	let current = $state<Pending | null>(null);

	function confirm(opts: ConfirmOptions): Promise<boolean> {
		return new Promise((resolve) => {
			current = {
				kind: 'confirm',
				title: opts.title,
				message: opts.message ?? '',
				confirmLabel: opts.confirmLabel ?? 'Confirm',
				danger: opts.danger ?? false,
				resolve
			};
		});
	}

	function prompt(opts: PromptOptions): Promise<string | null> {
		return new Promise((resolve) => {
			current = {
				kind: 'prompt',
				title: opts.title,
				message: opts.message ?? '',
				placeholder: opts.placeholder ?? '',
				initial: opts.initial ?? '',
				confirmLabel: opts.confirmLabel ?? 'OK',
				resolve
			};
		});
	}

	function accept(value?: string) {
		const c = current;
		if (!c) return;
		current = null;
		if (c.kind === 'confirm') c.resolve(true);
		else c.resolve(value ?? '');
	}

	function cancel() {
		const c = current;
		if (!c) return;
		current = null;
		if (c.kind === 'confirm') c.resolve(false);
		else c.resolve(null);
	}

	return {
		get current() {
			return current;
		},
		confirm,
		prompt,
		accept,
		cancel
	};
}

export const dialogs = createDialogs();
