import { get, post } from './http';

export interface SearchHit {
	id: string;
	title: string;
	field: 'title' | 'content';
	snippet: string;
}

/** Full-text search over document titles and block content within a workspace.
 * Each hit says which field matched and (for content) carries a snippet. */
export const searchContent = (workspaceId: string, q: string) =>
	get<SearchHit[]>(
		`/api/v1/workspaces/${workspaceId}/search/content?${new URLSearchParams({ q })}`
	);

/** Ask the workspace's ingested knowledge base a natural-language question and
 * get a RAG-grounded answer. */
export const askKnowledge = (workspaceId: string, query: string) =>
	post<{ result: string; mode: string }>(
		`/api/v1/workspaces/${workspaceId}/knowledge/query`,
		{ query }
	);
