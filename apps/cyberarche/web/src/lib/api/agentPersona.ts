/** Agent persona: workspace custom instructions + durable memories (ai-agent). */
import { del, get, patch, post, put } from './http';

export interface AgentInstructions {
	workspace: string | null;
	personal: string | null;
}

export interface AgentMemory {
	id: string;
	text: string;
	created_by: string;
	created_at: string;
	updated_at: string;
}

export type InstructionScope = 'workspace' | 'personal';

export const getInstructions = (workspaceId: string) =>
	get<AgentInstructions>(`/api/v1/workspaces/${workspaceId}/agent/instructions`);

export const setInstructions = (workspaceId: string, scope: InstructionScope, text: string) =>
	put<void>(`/api/v1/workspaces/${workspaceId}/agent/instructions`, { scope, text });

export const clearInstructions = (workspaceId: string, scope: InstructionScope) =>
	del<void>(`/api/v1/workspaces/${workspaceId}/agent/instructions?scope=${scope}`);

export const listMemories = (workspaceId: string) =>
	get<AgentMemory[]>(`/api/v1/workspaces/${workspaceId}/agent/memories`);

export const addMemory = (workspaceId: string, text: string) =>
	post<AgentMemory>(`/api/v1/workspaces/${workspaceId}/agent/memories`, { text });

export const updateMemory = (workspaceId: string, memoryId: string, text: string) =>
	patch<AgentMemory>(`/api/v1/workspaces/${workspaceId}/agent/memories/${memoryId}`, { text });

export const deleteMemory = (workspaceId: string, memoryId: string) =>
	del<void>(`/api/v1/workspaces/${workspaceId}/agent/memories/${memoryId}`);
