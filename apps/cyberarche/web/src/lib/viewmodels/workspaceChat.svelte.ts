/** Workspace-wide chat ViewModel (ai-agent spec): a conversation grounded in
 * the whole workspace, independent of any open document. Read-only — the
 * backend never edits documents, so this only appends messages and surfaces
 * the source documents each answer drew on. */

import { askWorkspaceChat, type ChatSource } from '$lib/api/chat';

export interface ChatMessage {
	role: 'user' | 'assistant';
	content: string;
	/** Source documents the answer drew on (assistant messages only). */
	sources?: ChatSource[];
}

export function createWorkspaceChat(workspaceId: string) {
	let messages = $state<ChatMessage[]>([]);
	let busy = $state(false);
	let error = $state<string | null>(null);

	const vm = {
		get messages() {
			return messages;
		},
		get busy() {
			return busy;
		},
		get error() {
			return error;
		},

		/** Send a question: append the user turn, ask the backend, then append
		 * the assistant turn with its sources. Recent turns are sent for context. */
		async send(text: string) {
			const instruction = text.trim();
			if (!instruction || busy) return;
			busy = true;
			error = null;
			// Snapshot history BEFORE adding the new user turn.
			const history = messages.map((m) => ({ role: m.role, content: m.content }));
			messages = [...messages, { role: 'user', content: instruction }];
			try {
				const { answer, sources } = await askWorkspaceChat(
					workspaceId,
					instruction,
					history
				);
				messages = [...messages, { role: 'assistant', content: answer, sources }];
			} catch (err) {
				error = (err as Error).message;
			} finally {
				busy = false;
			}
		}
	};
	return vm;
}

export type WorkspaceChatVM = ReturnType<typeof createWorkspaceChat>;

/** Open/close state for the workspace chat panel — a module singleton so the
 * sidebar button can open the panel the workspace layout renders (mirrors
 * settingsModal). */
export function createWorkspaceChatOpen() {
	let open = $state(false);

	return {
		get isOpen() {
			return open;
		},
		open() {
			open = true;
		},
		close() {
			open = false;
		}
	};
}

export const workspaceChatOpen = createWorkspaceChatOpen();
