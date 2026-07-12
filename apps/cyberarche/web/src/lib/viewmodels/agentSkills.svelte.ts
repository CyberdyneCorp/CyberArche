/** Saved agent skills ViewModel (ai-agent spec): list/create/delete skills and
 * expand one into a runnable instruction string. Used by the settings manager
 * and the agent panel's quick-run menu. */
import {
	deleteSkill,
	instantiateSkill,
	listSkills,
	saveSkill,
	type AgentSkill
} from '$lib/api/agentSkills';
import { ApiError } from '$lib/api/http';

export function createAgentSkills(workspaceId: string) {
	let skills = $state<AgentSkill[]>([]);
	let error = $state<string | null>(null);
	let busy = $state(false);

	function fail(e: unknown): void {
		error = e instanceof ApiError ? `${e.status}: ${e.message}` : String(e);
	}

	return {
		get skills() {
			return skills;
		},
		get error() {
			return error;
		},
		get busy() {
			return busy;
		},

		async load(): Promise<void> {
			try {
				skills = await listSkills(workspaceId);
			} catch (e) {
				fail(e);
			}
		},

		async create(name: string, instruction: string, description = ''): Promise<boolean> {
			if (!name.trim() || !instruction.trim()) return false;
			busy = true;
			error = null;
			try {
				skills = [await saveSkill(workspaceId, { name, instruction, description }), ...skills];
				return true;
			} catch (e) {
				fail(e);
				return false;
			} finally {
				busy = false;
			}
		},

		async remove(id: string): Promise<void> {
			try {
				await deleteSkill(workspaceId, id);
				skills = skills.filter((s) => s.id !== id);
			} catch (e) {
				fail(e);
			}
		},

		/** Expand a skill into an instruction; returns null on failure. */
		async run(id: string, values: Record<string, string>): Promise<string | null> {
			try {
				return (await instantiateSkill(workspaceId, id, values)).instruction;
			} catch (e) {
				fail(e);
				return null;
			}
		}
	};
}

export type AgentSkillsVM = ReturnType<typeof createAgentSkills>;
