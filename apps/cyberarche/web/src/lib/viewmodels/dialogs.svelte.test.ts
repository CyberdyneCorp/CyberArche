import { describe, expect, it } from 'vitest';

import { createDialogs } from './dialogs.svelte';

describe('dialogs ViewModel', () => {
	it('confirm resolves true on accept and false on cancel', async () => {
		const dialogs = createDialogs();

		const accepted = dialogs.confirm({ title: 'Delete?', confirmLabel: 'Delete', danger: true });
		expect(dialogs.current?.kind).toBe('confirm');
		dialogs.accept();
		expect(await accepted).toBe(true);
		expect(dialogs.current).toBeNull();

		const cancelled = dialogs.confirm({ title: 'Delete?' });
		dialogs.cancel();
		expect(await cancelled).toBe(false);
	});

	it('prompt resolves the typed value on accept and null on cancel', async () => {
		const dialogs = createDialogs();

		const named = dialogs.prompt({ title: 'New folder', initial: 'Draft' });
		expect(dialogs.current?.kind).toBe('prompt');
		dialogs.accept('Research');
		expect(await named).toBe('Research');

		const abandoned = dialogs.prompt({ title: 'New folder' });
		dialogs.cancel();
		expect(await abandoned).toBeNull();
	});
});
