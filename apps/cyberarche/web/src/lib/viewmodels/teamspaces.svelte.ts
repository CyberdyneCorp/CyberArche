/** Teamspaces + favourites ViewModel (teamspaces / favorites specs).
 * Backs the sidebar's Favorites and Teamspaces sections. */

import type { Document } from '$lib/api/documents';
import {
	createFolder,
	folderDocuments,
	listFolders,
	listPrivate,
	type Folder
} from '$lib/api/folders';
import { listSharedWithMe } from '$lib/api/sharing';
import {
	addFavorite,
	createTeamspace,
	listFavorites,
	listTeamspaces,
	removeFavorite,
	teamspaceDocuments,
	type Teamspace
} from '$lib/api/teamspaces';

export interface TeamspaceNode {
	teamspace: Teamspace;
	documents: Document[];
	expanded: boolean;
	loaded: boolean;
}

export interface FolderNode {
	folder: Folder;
	documents: Document[];
	expanded: boolean;
	loaded: boolean;
}

export function createTeamspaces(workspaceId: string) {
	let nodes = $state<TeamspaceNode[]>([]);
	let favorites = $state<Document[]>([]);
	let shared = $state<Document[]>([]);
	let privateDocs = $state<Document[]>([]);
	let folderNodes = $state<FolderNode[]>([]);
	let error = $state<string | null>(null);

	const favoriteIds = $derived(new Set(favorites.map((d) => d.id)));

	const vm = {
		get nodes() {
			return nodes;
		},
		get favorites() {
			return favorites;
		},
		/** Documents reachable only through a document-level grant. */
		get shared() {
			return shared;
		},
		/** The caller's own private (teamspace-less, folderless) documents. */
		get private() {
			return privateDocs;
		},
		/** Top-level folders in a scope: a teamspace id, or null for private. */
		foldersFor(teamspaceId: string | null): FolderNode[] {
			return folderNodes.filter(
				(n) => n.folder.teamspace_id === teamspaceId && n.folder.parent_folder_id === null
			);
		},
		get error() {
			return error;
		},
		isFavorite(documentId: string): boolean {
			return favoriteIds.has(documentId);
		},

		async load() {
			const [teamspaces, favs, sharedDocs, priv, folders] = await Promise.all([
				listTeamspaces(workspaceId),
				listFavorites(),
				listSharedWithMe(),
				listPrivate(workspaceId),
				listFolders(workspaceId)
			]);
			// Preserve expansion across reloads, and refresh the documents of any
			// node already expanded so a move shows up without collapsing the tree.
			const prevTs = new Map(nodes.map((n) => [n.teamspace.id, n]));
			nodes = await Promise.all(
				teamspaces.map(async (teamspace) => {
					const prev = prevTs.get(teamspace.id);
					if (prev?.loaded) {
						return {
							teamspace,
							documents: await teamspaceDocuments(teamspace.id),
							expanded: prev.expanded,
							loaded: true
						};
					}
					return { teamspace, documents: [], expanded: prev?.expanded ?? false, loaded: false };
				})
			);
			favorites = favs;
			shared = sharedDocs;
			privateDocs = priv;
			const prevF = new Map(folderNodes.map((n) => [n.folder.id, n]));
			folderNodes = await Promise.all(
				folders.map(async (folder) => {
					const prev = prevF.get(folder.id);
					if (prev?.loaded) {
						return {
							folder,
							documents: await folderDocuments(folder.id),
							expanded: prev.expanded,
							loaded: true
						};
					}
					return { folder, documents: [], expanded: prev?.expanded ?? false, loaded: false };
				})
			);
		},

		async toggleFolder(folderId: string) {
			const node = folderNodes.find((n) => n.folder.id === folderId);
			if (!node) return;
			node.expanded = !node.expanded;
			if (node.expanded && !node.loaded) {
				node.documents = await folderDocuments(folderId);
				node.loaded = true;
			}
		},

		async createFolder(name: string, teamspaceId: string | null): Promise<Folder | null> {
			error = null;
			try {
				const folder = await createFolder(workspaceId, name, teamspaceId);
				folderNodes = [
					...folderNodes,
					{ folder, documents: [], expanded: false, loaded: false }
				];
				return folder;
			} catch (err) {
				error = (err as Error).message;
				return null;
			}
		},

		async reloadFolder(folderId: string) {
			const node = folderNodes.find((n) => n.folder.id === folderId);
			if (!node) return;
			node.documents = await folderDocuments(folderId);
			node.loaded = true;
		},

		async toggle(teamspaceId: string) {
			const node = nodes.find((n) => n.teamspace.id === teamspaceId);
			if (!node) return;
			node.expanded = !node.expanded;
			if (node.expanded && !node.loaded) {
				node.documents = await teamspaceDocuments(teamspaceId);
				node.loaded = true;
			}
		},

		async create(name: string): Promise<Teamspace | null> {
			error = null;
			try {
				const teamspace = await createTeamspace(workspaceId, name);
				nodes = [
					...nodes,
					{ teamspace, documents: [], expanded: true, loaded: true }
				];
				return teamspace;
			} catch (err) {
				error = (err as Error).message;
				return null;
			}
		},

		/** Refresh a teamspace's documents (after creating one inside it). */
		async reload(teamspaceId: string) {
			const node = nodes.find((n) => n.teamspace.id === teamspaceId);
			if (!node) return;
			node.documents = await teamspaceDocuments(teamspaceId);
			node.loaded = true;
		},

		async toggleFavorite(document: Document) {
			if (vm.isFavorite(document.id)) {
				await removeFavorite(document.id);
				favorites = favorites.filter((d) => d.id !== document.id);
			} else {
				await addFavorite(document.id);
				favorites = [...favorites, document];
			}
		}
	};
	return vm;
}

export type TeamspacesVM = ReturnType<typeof createTeamspaces>;
