/** Saved agent skills: reusable, parameterized agent instructions (ai-agent). */
import { del, get, post, put } from './http';

export interface AgentSkill {
	id: string;
	name: string;
	description: string;
	instruction: string;
	variables: string[];
	created_by: string;
	created_at: string;
}

const base = (workspaceId: string) => `/api/v1/workspaces/${workspaceId}/agent/skills`;

export const listSkills = (workspaceId: string) => get<AgentSkill[]>(base(workspaceId));

export const saveSkill = (
	workspaceId: string,
	skill: { name: string; instruction: string; description?: string }
) => post<AgentSkill>(base(workspaceId), { description: '', ...skill });

export const updateSkill = (
	workspaceId: string,
	skillId: string,
	skill: { name: string; instruction: string; description?: string }
) => put<AgentSkill>(`${base(workspaceId)}/${skillId}`, { description: '', ...skill });

export const deleteSkill = (workspaceId: string, skillId: string) =>
	del<void>(`${base(workspaceId)}/${skillId}`);

/** Expand a skill's variables into a concrete instruction string (no LLM). */
export const instantiateSkill = (
	workspaceId: string,
	skillId: string,
	values: Record<string, string>
) =>
	post<{ instruction: string }>(`${base(workspaceId)}/${skillId}/instantiate`, {
		values
	});
