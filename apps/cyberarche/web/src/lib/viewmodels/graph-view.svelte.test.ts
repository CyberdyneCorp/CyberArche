import { describe, expect, it } from 'vitest';

import { createGraphView } from './graph-view.svelte';

describe('graph view store', () => {
	it('opens a scope and closes back to null', () => {
		const gv = createGraphView();
		expect(gv.current).toBeNull();

		gv.open({ kind: 'teamspace', id: 't1', name: 'Team' });
		expect(gv.current).toEqual({ kind: 'teamspace', id: 't1', name: 'Team' });

		gv.open({ kind: 'folder', id: 'f1', name: 'Notes' });
		expect(gv.current?.kind).toBe('folder');

		gv.close();
		expect(gv.current).toBeNull();
	});
});
