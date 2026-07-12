/** Autonomous scheduled agent tasks (autonomous-agents spec). */
import { del, get, patch, post } from './http';

export interface ScheduledTask {
	id: string;
	name: string;
	instruction: string;
	schedule_cron: string;
	document_id: string | null;
	enabled: boolean;
	next_run_at: string | null;
	owner_id: string;
	max_tool_rounds: number;
	max_wall_seconds: number;
	max_actions: number;
}

export interface TaskRun {
	id: string;
	trigger: string;
	outcome: string;
	document_id: string | null;
	detail: string;
	started_at: string;
	finished_at: string | null;
}

const base = (workspaceId: string) => `/api/v1/workspaces/${workspaceId}/agent/tasks`;

export const listTasks = (workspaceId: string) => get<ScheduledTask[]>(base(workspaceId));

export const createTask = (
	workspaceId: string,
	task: { name: string; instruction: string; schedule_cron: string; document_id?: string | null }
) => post<ScheduledTask>(base(workspaceId), { document_id: null, ...task });

export const setTaskEnabled = (workspaceId: string, taskId: string, enabled: boolean) =>
	patch<ScheduledTask>(`${base(workspaceId)}/${taskId}`, { enabled });

export const deleteTask = (workspaceId: string, taskId: string) =>
	del<void>(`${base(workspaceId)}/${taskId}`);

export const listTaskRuns = (workspaceId: string, taskId: string) =>
	get<TaskRun[]>(`${base(workspaceId)}/${taskId}/runs`);
