/** Workspace document index for wikilinks + the command palette: the full list
 * of accessible documents, resolved by title (case-insensitive). Loaded once per
 * workspace and refreshable after create/rename. A module-level singleton so the
 * inline renderer can resolve [[Title]] without prop-drilling. */

import { searchDocuments, type Document } from '$lib/api/documents';

export function createLinkIndex() {
	let workspaceId: string | null = null;
	let docs = $state<Document[]>([]);
	const byTitle = $derived(
		new Map(docs.map((d) => [d.title.trim().toLowerCase(), d]))
	);

	return {
		async load(ws: string) {
			workspaceId = ws;
			docs = await searchDocuments(ws, '', 500);
		},
		async refresh() {
			if (workspaceId) docs = await searchDocuments(workspaceId, '', 500);
		},
		get all() {
			return docs;
		},
		/** The href for a wikilink title, or null if no document matches. */
		hrefFor(title: string): string | null {
			const doc = byTitle.get(title.trim().toLowerCase());
			return doc ? `/w/${doc.workspace_id}/d/${doc.id}` : null;
		},
		/** Title-substring matches for autocomplete / palette (capped). */
		matches(query: string, limit = 8): Document[] {
			const q = query.trim().toLowerCase();
			const list = q ? docs.filter((d) => d.title.toLowerCase().includes(q)) : docs;
			return list.slice(0, limit);
		}
	};
}

export const linkIndex = createLinkIndex();
export type LinkIndexVM = ReturnType<typeof createLinkIndex>;
