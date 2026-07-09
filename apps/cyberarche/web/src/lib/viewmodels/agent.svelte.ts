/** Agent panel ViewModel (ai-agent spec 8.7): conversation with the
 * document's agent, insertable results, file ingestion, run history. */

import {
	askAgent,
	replaceBlockText,
	draftContent,
	ingestFile,
	insertBlocks,
	listAgentRuns,
	summarizeDocument,
	type AgentRun
} from '$lib/api/agent';

export interface AgentMessage {
	role: 'user' | 'agent';
	text: string;
	/** Block payloads offered for insertion (summaries, drafts). */
	blocks?: Record<string, unknown>[];
	inserted?: boolean;
}

export interface AgentPanelOptions {
	/** Apply blocks to the local editor document (a CRDT peer edit). When
	 * provided, Insert uses this instead of the server round-trip, so blocks
	 * appear immediately and sync — even offline. */
	insertLocal?: (blocks: Record<string, unknown>[]) => void;
}

export function createAgentPanel(documentId: string, options: AgentPanelOptions = {}) {
	let messages = $state<AgentMessage[]>([]);
	let busy = $state(false);
	let error = $state<string | null>(null);
	let runs = $state<AgentRun[]>([]);
	let ingesting = $state<'idle' | 'uploading' | 'done'>('idle');

	async function perform(label: string, action: () => Promise<AgentMessage>) {
		busy = true;
		error = null;
		messages = [...messages, { role: 'user', text: label }];
		try {
			const reply = await action();
			messages = [...messages, reply];
		} catch (err) {
			error = (err as Error).message;
		} finally {
			busy = false;
		}
	}

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
		get runs() {
			return runs;
		},
		get ingesting() {
			return ingesting;
		},

		/** Conversational ask. The reply carries insertable blocks, so every
		 * answer offers Insert / Replace / Copy (ai-agent spec). */
		async ask(instruction: string) {
			await perform(instruction, async () => {
				const { answer, blocks } = await askAgent(documentId, instruction);
				return { role: 'agent', text: answer, blocks };
			});
		},

		async summarize(blockIds?: string[]) {
			const label =
				blockIds && blockIds.length
					? `Summarize the selected block${blockIds.length > 1 ? 's' : ''}`
					: 'Summarize this document';
			await perform(label, async () => {
				const result = await summarizeDocument(documentId, blockIds);
				return {
					role: 'agent',
					text: blocksPreview(result.blocks),
					blocks: result.blocks
				};
			});
		},

		async draft(instruction: string) {
			await perform(`Draft: ${instruction}`, async () => {
				const result = await draftContent(documentId, instruction);
				return {
					role: 'agent',
					text: blocksPreview(result.blocks),
					blocks: result.blocks
				};
			});
		},

		/** Insert an agent result into the live document (CRDT peer edit
		 * on the backend — collaborators see it appear immediately). */
		async insert(message: AgentMessage) {
			if (!message.blocks?.length) return;
			if (options.insertLocal) {
				// Local CRDT peer edit: shows immediately and syncs, offline-safe.
				options.insertLocal(message.blocks);
			} else {
				await insertBlocks(documentId, message.blocks);
			}
			messages = messages.map((m) => (m === message ? { ...m, inserted: true } : m));
		},

		/** Replace the focused block's text with the answer, keeping its type. */
		async replaceSelection(message: AgentMessage, blockId: string | null) {
			if (!blockId) {
				error = 'Select a block in the document first.';
				return;
			}
			await replaceBlockText(documentId, blockId, message.text);
			messages = messages.map((m) => (m === message ? { ...m, inserted: true } : m));
		},

		async copy(message: AgentMessage) {
			await navigator.clipboard.writeText(message.text);
		},

		async ingest(file: File) {
			ingesting = 'uploading';
			error = null;
			try {
				const result = await ingestFile(documentId, file);
				messages = [
					...messages,
					{
						role: 'agent',
						text: `Ingested ${file.name} — ${result.blocks.length} block(s) added to the document and submitted to the knowledge base.`
					}
				];
				ingesting = 'done';
			} catch (err) {
				error = (err as Error).message;
				ingesting = 'idle';
			}
		},

		async loadRuns() {
			runs = await listAgentRuns(documentId);
		}
	};
	return vm;
}

function blocksPreview(blocks: Record<string, unknown>[]): string {
	const texts = blocks
		.map((block) => ((block.data as Record<string, unknown>)?.text as string) ?? '')
		.filter(Boolean);
	return texts.join('\n\n') || `${blocks.length} block(s) ready`;
}

export type AgentPanelVM = ReturnType<typeof createAgentPanel>;
