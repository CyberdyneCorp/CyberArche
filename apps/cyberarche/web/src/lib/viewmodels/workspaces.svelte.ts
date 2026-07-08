/** Workspaces ViewModel: list, create, current selection. */

import { createWorkspace, listWorkspaces, type Workspace } from '$lib/api/workspaces';

export function createWorkspaces() {
	let items = $state<Workspace[]>([]);
	let loaded = $state(false);

	return {
		get items() {
			return items;
		},
		get loaded() {
			return loaded;
		},
		byId(id: string): Workspace | undefined {
			return items.find((w) => w.id === id);
		},
		async load() {
			items = await listWorkspaces();
			loaded = true;
		},
		async create(name: string): Promise<Workspace> {
			const workspace = await createWorkspace(name);
			items = [...items, workspace];
			return workspace;
		}
	};
}

export const workspaces = createWorkspaces();
