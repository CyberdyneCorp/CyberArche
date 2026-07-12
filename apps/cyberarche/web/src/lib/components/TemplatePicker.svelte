<script lang="ts">
	/** Pick a page template to create a new document from (page-templates). */
	import { goto } from '$app/navigation';
	import {
		deleteTemplate,
		instantiateTemplate,
		listTemplates,
		type Template
	} from '$lib/api/templates';
	import { toasts } from '$lib/viewmodels/toasts.svelte';

	let { workspaceId, onclose }: { workspaceId: string; onclose: () => void } = $props();

	let templates = $state<Template[]>([]);
	let loading = $state(true);
	let busy = $state(false);

	async function refresh() {
		try {
			templates = await listTemplates(workspaceId);
		} catch {
			toasts.error("Couldn't load templates");
		} finally {
			loading = false;
		}
	}
	$effect(() => {
		void refresh();
	});

	async function use(t: Template) {
		if (busy) return;
		busy = true;
		try {
			const doc = await instantiateTemplate(workspaceId, t.id, t.name, null);
			onclose();
			await goto(`/w/${workspaceId}/d/${doc.id}`);
		} catch {
			toasts.error("Couldn't create from template");
			busy = false;
		}
	}
	async function remove(t: Template, event: MouseEvent) {
		event.stopPropagation();
		try {
			await deleteTemplate(t.id);
			templates = templates.filter((x) => x.id !== t.id);
		} catch {
			toasts.error("Couldn't delete template");
		}
	}
</script>

<svelte:window onkeydown={(e) => e.key === 'Escape' && onclose()} />

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="backdrop" role="presentation" onclick={onclose}>
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div class="panel" role="dialog" aria-label="New from template" tabindex="-1" onclick={(e) => e.stopPropagation()}>
		<header>
			<h2>New from template</h2>
			<button class="x" aria-label="Close" onclick={onclose}>✕</button>
		</header>
		<div class="list">
			{#if loading}
				<p class="empty">Loading…</p>
			{:else if templates.length === 0}
				<p class="empty">No templates yet. Open a document and choose “Save as template”.</p>
			{:else}
				{#each templates as t (t.id)}
					<div class="tpl">
						<button class="use" data-testid="template-item" disabled={busy} onclick={() => use(t)}>
							<span class="ic">▤</span>
							<span class="body">
								<span class="name">{t.name}</span>
								<span class="meta">{t.block_count} block{t.block_count === 1 ? '' : 's'}</span>
							</span>
						</button>
						<button class="rm" aria-label="Delete template" onclick={(e) => remove(t, e)}>🗑</button>
					</div>
				{/each}
			{/if}
		</div>
	</div>
</div>

<style>
	.backdrop {
		position: fixed;
		inset: 0;
		z-index: 80;
		display: grid;
		place-items: center;
		background: color-mix(in srgb, var(--bg1) 55%, transparent);
		backdrop-filter: blur(3px);
	}
	.panel {
		width: min(92vw, 420px);
		max-height: 70vh;
		display: flex;
		flex-direction: column;
		background: var(--bg2);
		border: 1px solid var(--line);
		border-radius: var(--r-block);
		box-shadow: var(--sh3);
		overflow: hidden;
	}
	header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 14px 16px;
		border-bottom: 1px solid var(--line);
	}
	h2 {
		margin: 0;
		font-size: 15px;
		color: var(--tx);
	}
	.x {
		width: 28px;
		height: 28px;
		border-radius: var(--r-control);
		color: var(--tx2);
	}
	.x:hover {
		background: var(--bg3);
		color: var(--tx);
	}
	.list {
		overflow-y: auto;
		padding: 8px;
	}
	.tpl {
		display: flex;
		align-items: center;
		border-radius: var(--r-control);
	}
	.tpl:hover {
		background: var(--bg3);
	}
	.use {
		flex: 1;
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 10px;
		text-align: left;
		min-width: 0;
	}
	.ic {
		color: var(--tx2);
	}
	.body {
		flex: 1;
		display: flex;
		flex-direction: column;
		min-width: 0;
	}
	.name {
		color: var(--tx);
		font-size: 13.5px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.meta {
		color: var(--tx3);
		font-size: 11.5px;
	}
	.rm {
		color: var(--tx3);
		padding: 3px 6px;
		border-radius: var(--r-control);
	}
	.rm:hover {
		background: var(--bg2);
		color: var(--rose);
	}
	.empty {
		margin: 0;
		padding: 24px 16px;
		text-align: center;
		font-size: 12.5px;
		color: var(--tx3);
		line-height: 1.5;
	}
</style>
