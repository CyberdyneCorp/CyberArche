/** Wikilink graph (wikilink-graph-view): the `[[…]]` link graph of a teamspace
 * or folder's documents. */
import { get } from './http';

export interface GraphNode {
	id: string;
	title: string;
}

export interface GraphEdge {
	source: string;
	target: string;
	type: string; // links_to | depends_on | explains | cites | similar | contradicts | mentions
	confidence: number;
	evidence: string;
	inferred: boolean;
}

export interface LinkGraph {
	nodes: GraphNode[];
	edges: GraphEdge[];
}

export const teamspaceGraph = (teamspaceId: string) =>
	get<LinkGraph>(`/api/v1/teamspaces/${teamspaceId}/graph`);

export const folderGraph = (folderId: string) =>
	get<LinkGraph>(`/api/v1/folders/${folderId}/graph`);

/** The graph with AI-inferred typed edges added (cached server-side per doc). */
export const teamspaceInferredGraph = (teamspaceId: string) =>
	get<LinkGraph>(`/api/v1/teamspaces/${teamspaceId}/graph/inferred`);

export const folderInferredGraph = (folderId: string) =>
	get<LinkGraph>(`/api/v1/folders/${folderId}/graph/inferred`);
