import { get, patch, post, request } from './http';

export interface AgentRun {
	id: string;
	user_id: string;
	model: string;
	prompt: string;
	tools_used: string[];
	outcome: string | null;
	started_at: string | null;
}

export interface BlocksResponse {
	blocks: Record<string, unknown>[];
	inserted: boolean;
}

export interface AgentToolCall {
	name: string;
	kind: 'mcp' | 'editing' | 'builtin';
	connector: string | null;
	arguments: Record<string, unknown>;
	result: string;
	ok: boolean;
}

export interface AskResult {
	answer: string;
	/** Insertable representation of the answer. */
	blocks: Record<string, unknown>[];
	/** Tool calls made this turn (built-in, editing, external MCP). */
	tool_calls: AgentToolCall[];
}

export interface HistoryTurn {
	role: 'user' | 'agent';
	content: string;
}

export const askAgent = (documentId: string, instruction: string, history: HistoryTurn[] = []) =>
	post<AskResult>(`/api/v1/documents/${documentId}/agent/ask`, { instruction, history });

export const summarizeDocument = (documentId: string, blockIds?: string[]) =>
	post<BlocksResponse>(`/api/v1/documents/${documentId}/agent/summarize`, {
		block_ids: blockIds ?? null
	});

export const draftContent = (documentId: string, instruction: string) =>
	post<BlocksResponse>(`/api/v1/documents/${documentId}/agent/draft`, { instruction });

export const insertBlocks = (documentId: string, blocks: Record<string, unknown>[]) =>
	post<BlocksResponse>(`/api/v1/documents/${documentId}/agent/blocks`, { blocks });

export const ingestFile = (documentId: string, file: File) => {
	const body = new FormData();
	body.append('file', file);
	return request<BlocksResponse>(`/api/v1/documents/${documentId}/agent/ingest`, {
		method: 'POST',
		body
	});
};

export const listAgentRuns = (documentId: string) =>
	get<AgentRun[]>(`/api/v1/documents/${documentId}/agent/runs`);

/** Replace a block's text via the agent's CRDT-peer edit path. */
export const replaceBlockText = (documentId: string, blockId: string, text: string) =>
	patch<{ block_id: string }>(`/api/v1/documents/${documentId}/agent/blocks/${blockId}`, {
		text
	});
