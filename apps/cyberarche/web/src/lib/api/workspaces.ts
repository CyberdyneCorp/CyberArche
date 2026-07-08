import { get, post } from './http';

export interface Workspace {
	id: string;
	name: string;
	created_by: string;
	created_at: string;
	rag_project_slug: string | null;
}

export const listWorkspaces = () => get<Workspace[]>('/api/v1/workspaces');
export const createWorkspace = (name: string) =>
	post<Workspace>('/api/v1/workspaces', { name });
export const getWorkspace = (id: string) => get<Workspace>(`/api/v1/workspaces/${id}`);
