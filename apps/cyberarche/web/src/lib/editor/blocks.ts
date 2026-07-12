/** Registers the built-in block types (12.1: adding one = one entry here). */

import DatabaseBlock from '$lib/components/editor/blocks/DatabaseBlock.svelte';
import DividerBlock from '$lib/components/editor/blocks/DividerBlock.svelte';
import CodeBlock from '$lib/components/editor/blocks/CodeBlock.svelte';
import EmbedBlock from '$lib/components/editor/blocks/EmbedBlock.svelte';
import ExcalidrawBlock from '$lib/components/editor/blocks/ExcalidrawBlock.svelte';
import ImageBlock from '$lib/components/editor/blocks/ImageBlock.svelte';
import LatexBlock from '$lib/components/editor/blocks/LatexBlock.svelte';
import MermaidBlock from '$lib/components/editor/blocks/MermaidBlock.svelte';
import TableBlock from '$lib/components/editor/blocks/TableBlock.svelte';
import TextBlocks from '$lib/components/editor/blocks/TextBlocks.svelte';
import WhiteboardBlock from '$lib/components/editor/blocks/WhiteboardBlock.svelte';
import { registerBlock } from './registry';

let registered = false;

export function registerBuiltinBlocks(): void {
	if (registered) return;
	registered = true;

	registerBlock({
		type: 'paragraph',
		label: 'Text',
		icon: '¶',
		group: 'text',
		hint: 'Plain paragraph',
		create: () => ({ text: '' }),
		component: TextBlocks
	});
	registerBlock({
		type: 'heading',
		label: 'Heading',
		icon: 'H',
		group: 'text',
		hint: 'Section heading',
		create: () => ({ text: '', level: 2 }),
		component: TextBlocks,
		markdownPrefix: /^(#{1,3})\s$/,
		// `#` -> h1, `##` -> h2, `###` -> h3 (block-editor spec).
		fromMarkdown: (match) => ({ text: '', level: match[1].length })
	});
	registerBlock({
		type: 'bulleted_list',
		label: 'Bulleted list',
		icon: '•',
		group: 'text',
		hint: 'Simple list',
		create: () => ({ text: '' }),
		component: TextBlocks,
		markdownPrefix: /^[-*]\s$/
	});
	registerBlock({
		type: 'numbered_list',
		label: 'Numbered list',
		icon: '1.',
		group: 'text',
		hint: 'Ordered list',
		create: () => ({ text: '' }),
		component: TextBlocks,
		markdownPrefix: /^1[.)]\s$/
	});
	registerBlock({
		type: 'todo',
		label: 'To-do',
		icon: '☐',
		group: 'text',
		hint: 'Checkbox item',
		create: () => ({ text: '', checked: false }),
		component: TextBlocks,
		markdownPrefix: /^\[\s?\]\s$/
	});
	registerBlock({
		type: 'callout',
		label: 'Callout',
		icon: '◆',
		group: 'text',
		hint: 'Highlighted note',
		create: () => ({ text: '' }),
		component: TextBlocks,
		markdownPrefix: /^>\s$/
	});
	registerBlock({
		type: 'quote',
		label: 'Quote',
		icon: '❝',
		group: 'text',
		hint: 'Pull quote',
		create: () => ({ text: '' }),
		component: TextBlocks
	});
	registerBlock({
		type: 'divider',
		label: 'Divider',
		icon: '—',
		group: 'text',
		hint: 'Horizontal rule',
		create: () => ({}),
		component: DividerBlock,
		markdownPrefix: /^---\s?$/
	});
	registerBlock({
		type: 'code',
		label: 'Code',
		icon: '⌘',
		group: 'technical',
		hint: 'Highlighted source',
		create: () => ({ source: '', language: 'python' }),
		component: CodeBlock,
		markdownPrefix: /^```\s?$/
	});
	registerBlock({
		type: 'latex',
		label: 'LaTeX',
		icon: '∑',
		group: 'technical',
		hint: 'Typeset math (KaTeX)',
		create: () => ({ source: '' }),
		component: LatexBlock,
		markdownPrefix: /^\$\$\s?$/
	});
	registerBlock({
		type: 'mermaid',
		label: 'Mermaid',
		icon: '⿻',
		group: 'technical',
		hint: 'Diagram from source',
		create: () => ({ source: '' }),
		component: MermaidBlock
	});
	registerBlock({
		type: 'excalidraw',
		label: 'Whiteboard',
		icon: '✦',
		group: 'media',
		hint: 'Excalidraw canvas + mind maps',
		create: () => ({ scene: '' }),
		component: ExcalidrawBlock
	});
	// Legacy hand-rolled canvas — kept registered (hidden from the slash menu) so
	// documents authored before the native Excalidraw block still render.
	registerBlock({
		type: 'whiteboard',
		label: 'Whiteboard (legacy)',
		icon: '✦',
		group: 'media',
		hint: 'Legacy canvas',
		hidden: true,
		create: () => ({ elements: {} }),
		component: WhiteboardBlock
	});
	registerBlock({
		type: 'table',
		label: 'Table',
		icon: '▦',
		group: 'technical',
		hint: 'Rows and columns',
		create: () => ({
			header: ['Column 1', 'Column 2'],
			rows: [['', '']]
		}),
		component: TableBlock
	});
	registerBlock({
		type: 'database',
		label: 'Database',
		icon: '▤',
		group: 'technical',
		hint: 'Typed rows with table & board views',
		create: () => ({ db: { properties: [], rows: [] } }),
		component: DatabaseBlock
	});
	registerBlock({
		type: 'image',
		label: 'Image',
		icon: '🖼',
		group: 'media',
		hint: 'Upload or embed by URL',
		create: () => ({ url: '', alt: '' }),
		component: ImageBlock
	});
	registerBlock({
		type: 'embed',
		label: 'Embed',
		icon: '🎬',
		group: 'media',
		hint: 'YouTube, Vimeo, or a link',
		create: () => ({ url: '' }),
		component: EmbedBlock
	});
}
