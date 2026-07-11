/** Document tree ViewModel: lazy-loaded nested tree per workspace,
 * create / rename / trash / restore, expansion state. */

import {
	createDocument,
	listChildren,
	listTrashed,
	purgeDocument,
	restoreDocument,
	retitleDocument,
	trashDocument,
	type Document
} from '$lib/api/documents';
import { docTitles } from './doc-titles';

export interface TreeNode {
	document: Document;
	children: TreeNode[];
	expanded: boolean;
	childrenLoaded: boolean;
}

function node(document: Document): TreeNode {
	return { document, children: [], expanded: false, childrenLoaded: false };
}

export function createDocumentTree() {
	let workspaceId = $state<string | null>(null);
	let roots = $state<TreeNode[]>([]);
	let trash = $state<Document[]>([]);

	/** The in-flight initial listing, if any. `open()` replaces `roots`
	 * wholesale, so a mutation racing it would be clobbered by a listing that
	 * predates the mutation — a created document could vanish from the sidebar.
	 * Mutations await this first. */
	let loading: Promise<void> | null = null;
	const settled = () => loading ?? Promise.resolve();

	function findNode(nodes: TreeNode[], id: string): TreeNode | null {
		for (const item of nodes) {
			if (item.document.id === id) return item;
			const found = findNode(item.children, id);
			if (found) return found;
		}
		return null;
	}

	function removeNode(nodes: TreeNode[], id: string): TreeNode[] {
		return nodes
			.filter((item) => item.document.id !== id)
			.map((item) => ({ ...item, children: removeNode(item.children, id) }));
	}

	const vm = {
		get workspaceId() {
			return workspaceId;
		},
		get roots() {
			return roots;
		},
		get trash() {
			return trash;
		},
		find(id: string): TreeNode | null {
			return findNode(roots, id);
		},

		async open(workspace: string) {
			workspaceId = workspace;
			loading = (async () => {
				const [documents, trashed] = await Promise.all([
					listChildren(workspace),
					listTrashed(workspace)
				]);
				roots = documents.map(node);
				trash = trashed;
			})();
			try {
				await loading;
			} finally {
				loading = null;
			}
		},

		async toggle(id: string) {
			const item = findNode(roots, id);
			if (!item) return;
			item.expanded = !item.expanded;
			if (item.expanded && !item.childrenLoaded) {
				await vm.loadChildren(id);
			}
		},

		async loadChildren(id: string) {
			const item = findNode(roots, id);
			if (!item || !workspaceId) return;
			item.children = (await listChildren(workspaceId, id)).map(node);
			item.childrenLoaded = true;
		},

		async create(
			title = '',
			parentId?: string,
			teamspaceId?: string
		): Promise<Document> {
			if (!workspaceId) throw new Error('no workspace open');
			await settled();
			const document = await createDocument(workspaceId, title, parentId, teamspaceId);
			if (teamspaceId) {
				// Teamspace documents are listed under their teamspace, not the tree.
				return document;
			}
			if (parentId) {
				const parent = findNode(roots, parentId);
				if (parent) {
					parent.children = [...parent.children, node(document)];
					parent.expanded = true;
					parent.childrenLoaded = true;
				}
			} else {
				roots = [...roots, node(document)];
			}
			return document;
		},

		async rename(id: string, title: string) {
			await settled();
			const updated = await retitleDocument(id, title);
			const item = findNode(roots, id);
			if (item) item.document = updated;
			// Publish the new title so other lists (sidebar teamspace/folder trees,
			// favorites) that hold their own copy reflect it without reloading.
			docTitles.set(id, updated.title);
		},

		async moveToTrash(id: string) {
			await settled();
			const trashed = await trashDocument(id);
			roots = removeNode(roots, id);
			trash = [...trash, trashed];
		},

		async restore(id: string) {
			await settled();
			const restored = await restoreDocument(id);
			trash = trash.filter((d) => d.id !== id);
			if (restored.parent_id === null) {
				roots = [...roots, node(restored)];
			} else if (workspaceId) {
				// Nested restore: reload the parent's children for correctness.
				const parent = findNode(roots, restored.parent_id);
				if (parent?.childrenLoaded) await vm.loadChildren(restored.parent_id);
			}
			return restored;
		},

		/** Permanently delete a trashed document; drops it from the trash list. */
		async purge(id: string) {
			await settled();
			await purgeDocument(id);
			trash = trash.filter((d) => d.id !== id);
		}
	};
	return vm;
}

export const documentTree = createDocumentTree();
