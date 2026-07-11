import { describe, expect, it } from 'vitest';

import { docTitles } from './doc-titles';

describe('live document titles', () => {
	it('overrides a loaded title after a rename, else falls back', () => {
		const doc = { id: 'd1', title: 'Untitled' };
		// Before any rename, the loaded title is used.
		expect(docTitles.titleOf(doc)).toBe('Untitled');

		// After rename, every list showing this doc reflects the new title, even
		// though its own loaded copy still says "Untitled".
		docTitles.set('d1', 'Integrals');
		expect(docTitles.titleOf(doc)).toBe('Integrals');
		expect(docTitles.titleOf({ id: 'd1', title: 'Untitled' })).toBe('Integrals');

		// An untouched document is unaffected.
		expect(docTitles.titleOf({ id: 'd2', title: 'Algebra' })).toBe('Algebra');
	});
});
