<script lang="ts">
	/** Version history (version-history spec): a timeline of a document's saved
	 * versions with inline rename, one-click restore, and a block-level compare
	 * view (added / removed / modified). Reuses the SettingsModal/GraphModal
	 * scrim+panel shell. */
	import { onMount } from 'svelte';
	import { createHistory, type HistoryVM } from '$lib/viewmodels/history.svelte';
	import { historyModal } from '$lib/viewmodels/historyModal.svelte';
	import { toasts } from '$lib/viewmodels/toasts.svelte';

	let { documentId }: { documentId: string } = $props();

	const vm: HistoryVM = createHistory(documentId);

	let editingId = $state<string | null>(null);
	let labelDraft = $state('');

	onMount(() => {
		void vm.load();
	});

	function startRename(id: string, current: string | null): void {
		editingId = id;
		labelDraft = current ?? '';
	}
	async function commitRename(id: string): Promise<void> {
		await vm.rename(id, labelDraft);
		editingId = null;
	}
	async function restore(id: string): Promise<void> {
		const done = await vm.restore(id);
		if (done) toasts.success('Restored this version');
	}
	function when(iso: string): string {
		return new Date(iso).toLocaleString();
	}
</script>

<svelte:window onkeydown={(e) => e.key === 'Escape' && historyModal.close()} />

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="scrim" role="presentation" onclick={() => historyModal.close()}>
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="panel"
		role="dialog"
		aria-label="Version history"
		tabindex="-1"
		data-testid="history-modal"
		onclick={(e) => e.stopPropagation()}
	>
		<header>
			<div class="title"><span class="ico">◷</span><span>Version history</span></div>
			<button class="close" aria-label="Close" onclick={() => historyModal.close()}>✕</button>
		</header>

		<div class="body">
			<div class="timeline">
				{#if vm.busy && vm.versions.length === 0}
					<p class="note">Loading versions…</p>
				{:else if vm.versions.length === 0}
					<p class="note">No saved versions yet.</p>
				{/if}
				{#each vm.versions as v (v.id)}
					<div class="version" class:active={vm.comparing === v.id} data-testid="history-version">
						<div class="v-main">
							<span class="seq">v{v.seq}</span>
							{#if editingId === v.id}
								<!-- svelte-ignore a11y_autofocus -->
								<input
									class="label-input"
									bind:value={labelDraft}
									autofocus
									placeholder="Name this version"
									data-testid="history-rename-input"
									onblur={() => commitRename(v.id)}
									onkeydown={(e) => {
										if (e.key === 'Enter') commitRename(v.id);
										else if (e.key === 'Escape') (editingId = null);
									}}
								/>
							{:else}
								<button
									class="label"
									class:unnamed={!v.label}
									title="Rename this version"
									data-testid="history-rename"
									onclick={() => startRename(v.id, v.label)}
								>
									{v.label ?? 'Untitled version'}
								</button>
							{/if}
						</div>
						<div class="v-meta">
							<span>{when(v.created_at)}</span>
							{#if v.created_by}<span class="author">· {v.created_by}</span>{/if}
							{#if v.restored_from}<span class="tag">restore</span>{/if}
						</div>
						<div class="v-actions">
							<button
								class="ghost"
								data-testid="history-diff"
								onclick={() => vm.diffAgainst(v.id)}>Compare</button
							>
							<button
								class="ghost"
								data-testid="history-restore"
								onclick={() => restore(v.id)}>Restore</button
							>
						</div>
					</div>
				{/each}
			</div>

			<div class="compare">
				{#if vm.diff}
					<div class="cmp-head">
						<span>Changes vs current document</span>
						<button class="close sm" aria-label="Close comparison" onclick={() => vm.closeDiff()}
							>✕</button
						>
					</div>
					<div class="diff" data-testid="history-diff-view">
						{#each vm.diff.removed as b (b.id)}
							<div class="row removed"><span class="mark">−</span>{b.data?.text ?? b.type}</div>
						{/each}
						{#each vm.diff.modified as m (m.id)}
							<div class="row modified">
								<span class="mark">~</span>
								<span class="before">{m.before}</span>
								<span class="arrow">→</span>
								<span class="after">{m.after}</span>
							</div>
						{/each}
						{#each vm.diff.added as b (b.id)}
							<div class="row added"><span class="mark">+</span>{b.data?.text ?? b.type}</div>
						{/each}
						{#if vm.diff.added.length + vm.diff.removed.length + vm.diff.modified.length === 0}
							<p class="note">No differences — this version matches the current document.</p>
						{/if}
					</div>
				{:else}
					<p class="note center">Select “Compare” on a version to see what changed.</p>
				{/if}
			</div>
		</div>

		{#if vm.error}
			<footer class="err">{vm.error}</footer>
		{/if}
	</div>
</div>

<style>
	.scrim {
		position: fixed;
		inset: 0;
		z-index: 80;
		display: grid;
		place-items: center;
		background: color-mix(in srgb, var(--bg1) 55%, transparent);
		backdrop-filter: blur(3px);
	}
	.panel {
		width: min(94vw, 920px);
		height: min(86vh, 680px);
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
		padding: 10px 14px;
		border-bottom: 1px solid var(--line);
	}
	.title {
		display: flex;
		align-items: center;
		gap: 8px;
		font-weight: 600;
		color: var(--tx);
	}
	.ico {
		color: var(--acc);
	}
	.close {
		width: 28px;
		height: 28px;
		border-radius: var(--r-control);
		color: var(--tx2);
	}
	.close.sm {
		width: 22px;
		height: 22px;
	}
	.close:hover {
		background: var(--bg3);
		color: var(--tx);
	}
	.body {
		flex: 1;
		display: flex;
		min-height: 0;
	}
	.timeline {
		width: 46%;
		min-width: 300px;
		border-right: 1px solid var(--line);
		overflow-y: auto;
		padding: 8px;
	}
	.version {
		padding: 10px;
		border: 1px solid transparent;
		border-radius: var(--r-control);
	}
	.version:hover {
		background: var(--bg1);
	}
	.version.active {
		border-color: var(--acc);
		background: var(--accbg2, var(--bg1));
	}
	.v-main {
		display: flex;
		align-items: center;
		gap: 8px;
	}
	.seq {
		font-size: 11px;
		font-weight: 600;
		color: var(--tx3);
		font-variant-numeric: tabular-nums;
	}
	.label {
		text-align: left;
		font-size: 13.5px;
		font-weight: 600;
		color: var(--tx);
		flex: 1;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.label.unnamed {
		font-weight: 500;
		color: var(--tx3);
	}
	.label:hover {
		color: var(--acc-strong, var(--acc));
	}
	.label-input {
		flex: 1;
		padding: 3px 7px;
		border: 1px solid var(--acc);
		border-radius: var(--r-control);
		background: var(--bg1);
		color: var(--tx);
		font-size: 13px;
	}
	.v-meta {
		display: flex;
		gap: 6px;
		align-items: center;
		margin-top: 3px;
		font-size: 11.5px;
		color: var(--tx3);
	}
	.author {
		color: var(--tx2);
	}
	.tag {
		font-size: 10px;
		text-transform: uppercase;
		letter-spacing: 0.03em;
		padding: 1px 5px;
		border-radius: var(--r-pill);
		background: var(--bg3);
		color: var(--tx2);
	}
	.v-actions {
		display: flex;
		gap: 6px;
		margin-top: 7px;
	}
	.ghost {
		padding: 4px 10px;
		border-radius: var(--r-control);
		border: 1px solid var(--line);
		color: var(--tx2);
		font-size: 12px;
	}
	.ghost:hover {
		background: var(--bg3);
		color: var(--tx);
	}
	.compare {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
		overflow: hidden;
	}
	.cmp-head {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 9px 12px;
		border-bottom: 1px solid var(--line);
		font-size: 12.5px;
		font-weight: 600;
		color: var(--tx2);
	}
	.diff {
		flex: 1;
		overflow-y: auto;
		padding: 10px 12px;
		display: flex;
		flex-direction: column;
		gap: 5px;
		font-size: 13px;
	}
	.row {
		display: flex;
		align-items: baseline;
		gap: 7px;
		padding: 5px 8px;
		border-radius: var(--r-control);
		line-height: 1.4;
	}
	.row .mark {
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}
	.row.added {
		background: color-mix(in srgb, #22c55e 16%, transparent);
		color: var(--tx);
	}
	.row.added .mark {
		color: #16a34a;
	}
	.row.removed {
		background: color-mix(in srgb, #ef4444 16%, transparent);
		color: var(--tx);
	}
	.row.removed .mark {
		color: #dc2626;
	}
	.row.modified {
		background: color-mix(in srgb, #f59e0b 14%, transparent);
		color: var(--tx);
	}
	.row.modified .mark {
		color: #d97706;
	}
	.row .before {
		text-decoration: line-through;
		color: var(--tx3);
	}
	.row .arrow {
		color: var(--tx3);
	}
	.note {
		color: var(--tx3);
		font-size: 12.5px;
		padding: 12px;
		margin: 0;
	}
	.note.center {
		display: grid;
		place-items: center;
		height: 100%;
		text-align: center;
	}
	.err {
		padding: 8px 14px;
		border-top: 1px solid var(--line);
		color: var(--rose, #dc2626);
		font-size: 12.5px;
	}
</style>
