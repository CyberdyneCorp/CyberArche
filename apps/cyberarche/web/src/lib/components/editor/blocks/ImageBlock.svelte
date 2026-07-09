<script lang="ts">
	import { page } from '$app/state';
	import type { BlockComponentProps } from '$lib/editor/registry';
	import type { EditorVM } from '$lib/viewmodels/editor.svelte';
	import { toasts } from '$lib/viewmodels/toasts.svelte';
	import AuthImage from '../AuthImage.svelte';

	let { block, editor }: BlockComponentProps = $props();
	// svelte-ignore state_referenced_locally
	const vm = editor as EditorVM; // the VM is a stable singleton for this block

	const url = $derived((block.data.url as string) ?? '');
	const alt = $derived((block.data.alt as string) ?? '');
	// Our own served files sit behind bearer auth; external URLs load directly.
	const isInternal = $derived(url.startsWith('/api/'));
	const workspaceId = $derived(page.params.workspaceId ?? '');

	let urlDraft = $state('');
	let uploading = $state(false);
	let fileInput = $state<HTMLInputElement | null>(null);

	function applyUrl() {
		const next = urlDraft.trim();
		if (next) vm.updateData(block.id, { url: next });
	}

	async function onFileChosen(event: Event) {
		const file = (event.target as HTMLInputElement).files?.[0];
		if (!file || !workspaceId) return;
		uploading = true;
		try {
			const { uploadImage } = await import('$lib/api/files');
			const uploaded = await uploadImage(workspaceId, file);
			vm.updateData(block.id, { url: uploaded.url });
		} catch (error) {
			toasts.error((error as Error).message || "Couldn't upload image");
		} finally {
			uploading = false;
			if (fileInput) fileInput.value = '';
		}
	}
</script>

<div class="image-block" data-testid="image-block" role="group" onfocusin={() => vm.focus(block.id)}>
	{#if url}
		{#if isInternal}
			<AuthImage src={url} {alt} />
		{:else}
			<img src={url} {alt} data-testid="image-external" />
		{/if}
		<input
			class="caption"
			placeholder="Add a caption…"
			value={alt}
			oninput={(e) => vm.updateData(block.id, { alt: (e.target as HTMLInputElement).value })}
			data-testid="image-caption"
		/>
		<button class="change" onclick={() => vm.updateData(block.id, { url: '' })}>Replace</button>
	{:else}
		<div class="picker">
			<div class="row">
				<input
					class="url-input"
					placeholder="Paste an image URL…"
					bind:value={urlDraft}
					onkeydown={(e) => e.key === 'Enter' && applyUrl()}
					data-testid="image-url-input"
				/>
				<button class="btn" onclick={applyUrl} data-testid="image-url-apply">Embed</button>
			</div>
			<div class="or">or</div>
			<button
				class="btn upload"
				onclick={() => fileInput?.click()}
				disabled={uploading}
				data-testid="image-upload">{uploading ? 'Uploading…' : 'Upload an image'}</button
			>
			<input
				bind:this={fileInput}
				type="file"
				accept="image/png,image/jpeg,image/gif,image/webp"
				class="hidden-file"
				onchange={onFileChosen}
				data-testid="image-file-input"
			/>
		</div>
	{/if}
</div>

<style>
	.image-block :global(img),
	.image-block img {
		max-width: 100%;
		border-radius: var(--r-block, 8px);
		display: block;
	}
	.caption {
		display: block;
		width: 100%;
		margin-top: 6px;
		border: none;
		background: transparent;
		color: var(--tx3);
		font-size: 13px;
		text-align: center;
	}
	.caption:focus {
		outline: none;
		color: var(--tx2);
	}
	.change {
		margin-top: 4px;
		font-size: 11px;
		color: var(--tx3);
	}
	.change:hover {
		color: var(--tx);
	}
	.picker {
		border: 1px dashed var(--line2, var(--line));
		border-radius: var(--r-block, 8px);
		padding: 16px;
		display: flex;
		flex-direction: column;
		gap: 8px;
		align-items: center;
		background: var(--bg1);
	}
	.row {
		display: flex;
		gap: 6px;
		width: 100%;
		max-width: 460px;
	}
	.url-input {
		flex: 1;
		padding: 7px 10px;
		border: 1px solid var(--line);
		border-radius: 8px;
		background: var(--bg0);
		color: var(--tx);
		font-size: 13px;
	}
	.btn {
		padding: 7px 12px;
		border-radius: 8px;
		background: var(--acc, #4f46e5);
		color: #fff;
		font-size: 13px;
	}
	.btn:hover {
		filter: brightness(1.08);
	}
	.btn.upload {
		background: var(--bg2);
		color: var(--tx);
	}
	.or {
		color: var(--tx3);
		font-size: 11px;
	}
	.hidden-file {
		display: none;
	}
</style>
