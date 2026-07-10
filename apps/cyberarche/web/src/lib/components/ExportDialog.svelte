<script lang="ts">
	import { getBlob } from '$lib/api/http';
	import type { BlockData } from '$lib/editor/registry';
	import {
		blobToDataUrl,
		downloadTextFile,
		hasTables,
		internalImageUrls,
		safeFilename,
		tablesToCsv,
		toMarkdown,
		type ExportFormat
	} from '$lib/editor/export';
	import { toasts } from '$lib/viewmodels/toasts.svelte';

	let {
		title,
		blocks,
		onclose
	}: { title: string; blocks: BlockData[]; onclose: () => void } = $props();

	let format = $state<ExportFormat>('pdf');
	let busy = $state(false);

	/** Fetch our served images and encode them as data URIs so exported
	 * Markdown is self-contained (auth-gated URLs won't work outside the app). */
	async function inlineImages(): Promise<Map<string, string>> {
		const map = new Map<string, string>();
		for (const url of internalImageUrls(blocks)) {
			try {
				map.set(url, await blobToDataUrl(await getBlob(url)));
			} catch {
				/* fall back to the URL if the image can't be fetched */
			}
		}
		return map;
	}

	const FORMATS: { value: ExportFormat; label: string; hint: string }[] = [
		{ value: 'pdf', label: 'PDF', hint: 'Print-ready, as shown on screen' },
		{ value: 'markdown', label: 'Markdown', hint: 'Portable .md text' },
		{ value: 'csv', label: 'CSV', hint: 'This document’s tables' }
	];

	async function run() {
		const name = safeFilename(title);
		if (format === 'markdown') {
			busy = true;
			try {
				const images = await inlineImages();
				downloadTextFile(`${name}.md`, toMarkdown(title, blocks, images), 'text/markdown');
				toasts.success('Exported Markdown');
				onclose();
			} finally {
				busy = false;
			}
		} else if (format === 'csv') {
			if (!hasTables(blocks)) {
				toasts.error('No tables in this document to export as CSV');
				return;
			}
			downloadTextFile(`${name}.csv`, tablesToCsv(blocks), 'text/csv');
			toasts.success('Exported CSV');
			onclose();
		} else {
			// PDF: close first so the dialog isn't in the printout, then print.
			// A print stylesheet leaves only the document canvas visible.
			onclose();
			setTimeout(() => window.print(), 60);
		}
	}
</script>

<div class="backdrop" role="presentation" onclick={onclose}>
	<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
	<div
		class="dialog"
		role="dialog"
		aria-modal="true"
		aria-label="Export document"
		tabindex="-1"
		data-testid="export-dialog"
		onclick={(e) => e.stopPropagation()}
		onkeydown={(e) => e.key === 'Escape' && onclose()}
	>
		<div class="head">
			<h2>Export</h2>
			<button class="x" aria-label="Close" onclick={onclose}>✕</button>
		</div>

		<div class="field">
			<span class="label">Format</span>
			<div class="options">
				{#each FORMATS as f (f.value)}
					<label class="opt" class:selected={format === f.value}>
						<input type="radio" name="export-format" value={f.value} bind:group={format} />
						<span class="opt-label">{f.label}</span>
						<span class="opt-hint">{f.hint}</span>
					</label>
				{/each}
			</div>
		</div>

		<div class="actions">
			<button class="btn ghost" data-testid="export-cancel" onclick={onclose}>Cancel</button>
			<button class="btn" data-testid="export-run" disabled={busy} onclick={run}>
				{busy ? 'Exporting…' : 'Export'}
			</button>
		</div>
	</div>
</div>

<style>
	.backdrop {
		position: fixed;
		inset: 0;
		z-index: 1500;
		display: grid;
		place-items: center;
		background: rgba(0, 0, 0, 0.4);
		padding: 16px;
	}
	.dialog {
		width: min(420px, 100%);
		background: var(--bg1);
		color: var(--tx);
		border: 1px solid var(--line);
		border-radius: 14px;
		padding: 18px 20px 20px;
		box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
	}
	.head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 14px;
	}
	.head h2 {
		margin: 0;
		font-size: 16px;
		font-weight: 600;
	}
	.x {
		color: var(--tx3);
		font-size: 13px;
		padding: 2px 6px;
		border-radius: 6px;
	}
	.x:hover {
		background: var(--bg2);
		color: var(--tx);
	}
	.label {
		display: block;
		font-size: 11px;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--tx3);
		margin-bottom: 8px;
	}
	.options {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}
	.opt {
		display: grid;
		grid-template-columns: auto 1fr;
		grid-template-areas: 'radio label' 'radio hint';
		column-gap: 10px;
		align-items: center;
		padding: 9px 12px;
		border: 1px solid var(--line);
		border-radius: 10px;
		cursor: pointer;
	}
	.opt:hover {
		background: var(--bg2);
	}
	.opt.selected {
		border-color: var(--acc);
		background: var(--accbg);
	}
	.opt input {
		grid-area: radio;
	}
	.opt-label {
		grid-area: label;
		font-size: 13px;
		font-weight: 500;
	}
	.opt-hint {
		grid-area: hint;
		font-size: 11px;
		color: var(--tx3);
	}
	.actions {
		display: flex;
		justify-content: flex-end;
		gap: 8px;
		margin-top: 18px;
	}
	.btn {
		padding: 7px 16px;
		border-radius: 8px;
		font-size: 13px;
		font-weight: 500;
		background: var(--acc);
		color: #fff;
	}
	.btn:hover {
		filter: brightness(1.08);
	}
	.btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
		filter: none;
	}
	.btn.ghost {
		background: transparent;
		color: var(--tx2);
	}
	.btn.ghost:hover {
		background: var(--bg2);
		filter: none;
	}
</style>
