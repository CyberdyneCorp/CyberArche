/** Teamspaces + favourites ViewModel (teamspaces / favorites specs).
 * Backs the sidebar's Favorites and Teamspaces sections. */

import type { Document } from '$lib/api/documents';
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

export function createTeamspaces(workspaceId: string) {
	let nodes = $state<TeamspaceNode[]>([]);
	let favorites = $state<Document[]>([]);
	let shared = $state<Document[]>([]);
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
		get error() {
			return error;
		},
		isFavorite(documentId: string): boolean {
			return favoriteIds.has(documentId);
		},

		async load() {
			const [teamspaces, favs, sharedDocs] = await Promise.all([
				listTeamspaces(workspaceId),
				listFavorites(),
				listSharedWithMe()
			]);
			nodes = teamspaces.map((teamspace) => ({
				teamspace,
				documents: [],
				expanded: false,
				loaded: false
			}));
			favorites = favs;
			shared = sharedDocs;
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
