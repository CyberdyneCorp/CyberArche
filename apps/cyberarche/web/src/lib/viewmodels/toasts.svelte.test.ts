import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { createToasts } from './toasts.svelte';

describe('toasts ViewModel', () => {
	beforeEach(() => vi.useFakeTimers());
	afterEach(() => vi.useRealTimers());

	it('pushes toasts and auto-dismisses after the ttl', () => {
		const toasts = createToasts();

		toasts.success('Deleted');
		expect(toasts.items.map((t) => [t.message, t.kind])).toEqual([['Deleted', 'success']]);

		vi.advanceTimersByTime(4000);
		expect(toasts.items).toEqual([]);
	});

	it('dismiss removes a specific toast and each gets a distinct id', () => {
		const toasts = createToasts();

		const a = toasts.error('One');
		const b = toasts.info('Two');
		expect(a).not.toBe(b);
		expect(toasts.items).toHaveLength(2);

		toasts.dismiss(a);
		expect(toasts.items.map((t) => t.id)).toEqual([b]);
	});
});
