import { post } from './http';

export interface ChatSource {
	id: string;
	title: string;
}

export interface ChatResult {
	answer: string;
	/** The source documents the answer drew on (clickable in the UI). */
	sources: ChatSource[];
}

export interface ChatHistoryTurn {
	role: 'user' | 'assistant';
	content: string;
}

/** Ask the workspace-wide chat a question, grounded in the workspace's RAG
 * knowledge and documents. Read-only — it never edits anything. */
export const askWorkspaceChat = (
	workspaceId: string,
	instruction: string,
	history: ChatHistoryTurn[] = []
) =>
	post<ChatResult>(`/api/v1/workspaces/${workspaceId}/chat`, {
		instruction,
		history
	});
