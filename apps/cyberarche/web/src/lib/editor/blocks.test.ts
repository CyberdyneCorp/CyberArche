import { describe, expect, it } from 'vitest';

import { registerBuiltinBlocks } from './blocks';
import { allBlockDefinitions, blockDefinition } from './registry';

describe('built-in block registration', () => {
	registerBuiltinBlocks();

	// The slash menu lists non-hidden definitions (editor VM `slashMatches`
	// filters `!hidden`); this mirrors that filter.
	const insertable = () => allBlockDefinitions().filter((d) => !d.hidden).map((d) => d.type);

	it('registers the collection-backed database and exposes it in the slash menu', () => {
		expect(insertable()).toContain('collection_view');
		const def = blockDefinition('collection_view');
		expect(def?.label).toBe('Database');
		expect(def?.component).toBeTruthy();
		expect(def?.create()).toEqual({ collection_id: '', view_id: '' });
	});

	it('keeps the legacy database registered but hidden so old docs still render', () => {
		const legacy = blockDefinition('database');
		expect(legacy).toBeDefined();
		expect(legacy?.hidden).toBe(true);
		// Still has a component so blocks in existing documents render.
		expect(legacy?.component).toBeTruthy();
		// Excluded from the slash menu.
		expect(insertable()).not.toContain('database');
	});
});
