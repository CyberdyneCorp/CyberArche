/** Document-import flow (document-import spec, ViewModel): upload a file, insert
 * the created document(s) into the sidebar tree, and hand back the first one so
 * the caller can navigate to it. DOM-free and dependency-injected so it is
 * unit-testable; the Sidebar owns the hidden <input>, navigation, and toasts. */

import type { Document } from '$lib/api/documents';
import { importFile } from '$lib/api/import';
import { documentTree } from '$lib/viewmodels/document-tree.svelte';

/** File extensions the importer accepts (used for the <input accept> filter).
 * A PDF imports as a document; a CSV/Excel sheet imports as a collection
 * embedded in a document; a Notion `.zip` becomes a tree of documents. */
export const IMPORT_ACCEPT = '.md,.markdown,.txt,.docx,.pdf,.csv,.xlsx,.zip';

/** Upload `file`, add every created document to the tree (roots land under
 * Private), and return the first created document for navigation — or null when
 * the import produced no document. Throws on API failure so the caller can toast. */
export async function importDocuments(
	workspaceId: string,
	file: File
): Promise<Document | null> {
	const docs = await importFile(workspaceId, file);
	for (const doc of docs) documentTree.addRoot(doc);
	return docs[0] ?? null;
}
