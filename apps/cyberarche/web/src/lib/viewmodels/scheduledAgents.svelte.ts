/** Autonomous scheduled agents ViewModel (autonomous-agents spec): create,
 * list, enable/disable, and delete background agent tasks + view run history. */
import {
	createTask,
	deleteTask,
	listTaskRuns,
	listTasks,
	setTaskEnabled,
	type ScheduledTask,
	type TaskRun
} from '$lib/api/scheduledAgents';
import { ApiError } from '$lib/api/http';

export function createScheduledAgents(workspaceId: string) {
	let tasks = $state<ScheduledTask[]>([]);
	let runs = $state<Record<string, TaskRun[]>>({});
	let error = $state<string | null>(null);
	let busy = $state(false);

	function fail(e: unknown): void {
		error = e instanceof ApiError ? `${e.status}: ${e.message}` : String(e);
	}

	return {
		get tasks() {
			return tasks;
		},
		get runs() {
			return runs;
		},
		get error() {
			return error;
		},
		get busy() {
			return busy;
		},

		async load(): Promise<void> {
			try {
				tasks = await listTasks(workspaceId);
			} catch (e) {
				fail(e);
			}
		},

		async create(
			name: string,
			instruction: string,
			schedule_cron: string,
			documentId?: string | null
		): Promise<boolean> {
			if (!name.trim() || !instruction.trim() || !schedule_cron.trim()) return false;
			busy = true;
			error = null;
			try {
				tasks = [
					await createTask(workspaceId, {
						name,
						instruction,
						schedule_cron,
						document_id: documentId || null
					}),
					...tasks
				];
				return true;
			} catch (e) {
				fail(e);
				return false;
			} finally {
				busy = false;
			}
		},

		async toggle(task: ScheduledTask): Promise<void> {
			try {
				const updated = await setTaskEnabled(workspaceId, task.id, !task.enabled);
				tasks = tasks.map((t) => (t.id === task.id ? updated : t));
			} catch (e) {
				fail(e);
			}
		},

		async remove(id: string): Promise<void> {
			try {
				await deleteTask(workspaceId, id);
				tasks = tasks.filter((t) => t.id !== id);
			} catch (e) {
				fail(e);
			}
		},

		async loadRuns(id: string): Promise<void> {
			try {
				runs = { ...runs, [id]: await listTaskRuns(workspaceId, id) };
			} catch (e) {
				fail(e);
			}
		}
	};
}

export type ScheduledAgentsVM = ReturnType<typeof createScheduledAgents>;
