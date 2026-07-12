/** Agent persona settings ViewModel (ai-agent spec): edit a workspace's custom
 * instructions (shared + personal layers) and manage its durable memories. */
import {
	addMemory,
	clearInstructions,
	deleteMemory,
	getInstructions,
	listMemories,
	setInstructions,
	type AgentMemory,
	type InstructionScope
} from '$lib/api/agentPersona';
import { ApiError } from '$lib/api/http';

export function createAgentPersona(workspaceId: string) {
	let workspaceText = $state('');
	let personalText = $state('');
	let memories = $state<AgentMemory[]>([]);
	let error = $state<string | null>(null);
	let busy = $state(false);

	function fail(e: unknown): void {
		error = e instanceof ApiError ? `${e.status}: ${e.message}` : String(e);
	}

	return {
		get workspaceText() {
			return workspaceText;
		},
		set workspaceText(v: string) {
			workspaceText = v;
		},
		get personalText() {
			return personalText;
		},
		set personalText(v: string) {
			personalText = v;
		},
		get memories() {
			return memories;
		},
		get error() {
			return error;
		},
		get busy() {
			return busy;
		},

		async load(): Promise<void> {
			try {
				const [instructions, mems] = await Promise.all([
					getInstructions(workspaceId),
					listMemories(workspaceId)
				]);
				workspaceText = instructions.workspace ?? '';
				personalText = instructions.personal ?? '';
				memories = mems;
			} catch (e) {
				fail(e);
			}
		},

		async saveInstructions(scope: InstructionScope): Promise<void> {
			busy = true;
			error = null;
			const text = scope === 'workspace' ? workspaceText : personalText;
			try {
				if (text.trim()) await setInstructions(workspaceId, scope, text);
				else await clearInstructions(workspaceId, scope);
			} catch (e) {
				fail(e);
			} finally {
				busy = false;
			}
		},

		async addMemory(text: string): Promise<boolean> {
			if (!text.trim()) return false;
			busy = true;
			error = null;
			try {
				memories = [await addMemory(workspaceId, text.trim()), ...memories];
				return true;
			} catch (e) {
				fail(e);
				return false;
			} finally {
				busy = false;
			}
		},

		async removeMemory(id: string): Promise<void> {
			try {
				await deleteMemory(workspaceId, id);
				memories = memories.filter((m) => m.id !== id);
			} catch (e) {
				fail(e);
			}
		}
	};
}

export type AgentPersonaVM = ReturnType<typeof createAgentPersona>;
