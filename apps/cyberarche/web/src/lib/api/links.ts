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
}

export interface LinkGraph {
	nodes: GraphNode[];
	edges: GraphEdge[];
}

export const teamspaceGraph = (teamspaceId: string) =>
	get<LinkGraph>(`/api/v1/teamspaces/${teamspaceId}/graph`);

export const folderGraph = (folderId: string) =>
	get<LinkGraph>(`/api/v1/folders/${folderId}/graph`);
