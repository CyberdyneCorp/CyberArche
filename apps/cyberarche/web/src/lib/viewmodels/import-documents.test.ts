import { beforeEach, describe, expect, it, vi } from 'vitest';

import { importDocuments } from './import-documents';

vi.mock('$lib/api/import', () => ({ importFile: vi.fn() }));
vi.mock('$lib/viewmodels/document-tree.svelte', () => ({
	documentTree: { addRoot: vi.fn() }
}));

import { importFile } from '$lib/api/import';
import { documentTree } from '$lib/viewmodels/document-tree.svelte';

const ROOT = { id: 'doc-1', title: 'Area', parent_id: null, teamspace_id: null };
const CHILD = { id: 'doc-2', title: 'Page', parent_id: 'doc-1', teamspace_id: null };

describe('importDocuments', () => {
	beforeEach(() => vi.clearAllMocks());

	it('uploads the file, adds every created doc to the tree, returns the first', async () => {
		(importFile as ReturnType<typeof vi.fn>).mockResolvedValue([ROOT, CHILD]);

		const first = await importDocuments('ws-1', new File(['x'], 'export.zip'));

		expect(importFile).toHaveBeenCalledWith('ws-1', expect.any(File));
		expect(documentTree.addRoot).toHaveBeenCalledTimes(2);
		expect(documentTree.addRoot).toHaveBeenNthCalledWith(1, ROOT);
		expect(documentTree.addRoot).toHaveBeenNthCalledWith(2, CHILD);
		expect(first).toBe(ROOT);
	});

	it('returns null when the import produced no document', async () => {
		(importFile as ReturnType<typeof vi.fn>).mockResolvedValue([]);

		const first = await importDocuments('ws-1', new File(['x'], 'empty.md'));

		expect(first).toBeNull();
		expect(documentTree.addRoot).not.toHaveBeenCalled();
	});

	it('propagates API errors to the caller', async () => {
		(importFile as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('boom'));

		await expect(importDocuments('ws-1', new File(['x'], 'a.md'))).rejects.toThrow('boom');
	});
});
