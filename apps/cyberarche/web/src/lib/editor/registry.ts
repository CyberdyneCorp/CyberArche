/** Block registry (architecture-quality spec 12.1).
 *
 * Adding a block type = one register() call with its component and factory.
 * The editor engine, slash menu, CRDT sync, and persistence never change
 * per block type. Types mirror the backend whitelist (domain/blocks.py).
 */

import type { Component } from 'svelte';

export interface BlockData {
	id: string;
	type: string;
	data: Record<string, unknown>;
}

export interface BlockDefinition {
	type: string;
	label: string;
	icon: string;
	group: 'text' | 'technical' | 'media';
	/** Shown in the slash menu; keep to a few words. */
	hint: string;
	create(): Record<string, unknown>;
	component: Component<BlockComponentProps>;
	/** Markdown-style input prefix that transforms a paragraph, e.g. "# ". */
	markdownPrefix?: RegExp;
}

export interface BlockComponentProps {
	block: BlockData;
	editor: unknown; // EditorVM — typed loosely to avoid circular imports
}

const definitions = new Map<string, BlockDefinition>();

export function registerBlock(definition: BlockDefinition): void {
	if (definitions.has(definition.type)) {
		throw new Error(`block type already registered: ${definition.type}`);
	}
	definitions.set(definition.type, definition);
}

export function blockDefinition(type: string): BlockDefinition | undefined {
	return definitions.get(type);
}

export function allBlockDefinitions(): BlockDefinition[] {
	return [...definitions.values()];
}

export function markdownTransforms(): BlockDefinition[] {
	return allBlockDefinitions().filter((d) => d.markdownPrefix);
}

export function newBlock(type: string): BlockData {
	const definition = definitions.get(type);
	if (!definition) throw new Error(`unknown block type: ${type}`);
	return { id: crypto.randomUUID().replaceAll('-', ''), type, data: definition.create() };
}
