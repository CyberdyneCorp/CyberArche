/** Agent panel ViewModel (ai-agent spec 8.7): conversation with the
 * document's agent, insertable results, file ingestion, run history. */

import {
	askAgent,
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

export function createAgentPanel(documentId: string) {
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

		async ask(instruction: string) {
			await perform(instruction, async () => {
				const { answer } = await askAgent(documentId, instruction);
				return { role: 'agent', text: answer };
			});
		},

		async summarize() {
			await perform('Summarize this document', async () => {
				const result = await summarizeDocument(documentId);
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
			await insertBlocks(documentId, message.blocks);
			messages = messages.map((m) => (m === message ? { ...m, inserted: true } : m));
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
