<script lang="ts">
	import { goto } from '$app/navigation';
	import { documentTree } from '$lib/viewmodels/document-tree.svelte';
	import {
		createMeetingNotes_VM,
		meetingNotesModal,
		type MeetingNotesVM,
		type MonthGroup
	} from '$lib/viewmodels/meetingNotesModal.svelte';

	let { workspaceId }: { workspaceId: string } = $props();

	let vm = $state<MeetingNotesVM | null>(null);

	$effect(() => {
		const model = createMeetingNotes_VM(workspaceId);
		vm = model;
		model.load();
	});

	function onKeydown(event: KeyboardEvent) {
		if (event.key === 'Escape') meetingNotesModal.close();
	}

	function monthLabel(group: MonthGroup): string {
		if (group.key === 'undated') return 'Undated';
		return new Date(Date.UTC(group.year, group.month0, 1)).toLocaleDateString(undefined, {
			month: 'long',
			year: 'numeric',
			timeZone: 'UTC'
		});
	}

	/** Day + time only — the month/year already lives in the group header. */
	function shortWhen(iso: string | null): string {
		if (!iso) return '';
		const date = new Date(iso);
		if (Number.isNaN(date.getTime())) return iso;
		return date.toLocaleString(undefined, {
			weekday: 'short',
			day: 'numeric',
			hour: '2-digit',
			minute: '2-digit'
		});
	}

	/** Recordings ready to turn into a doc read as a positive state; anything
	 * still processing reads as pending. */
	function isReady(status: string): boolean {
		return status === 'completed' || status === 'ready';
	}

	async function generate(recordingId: string) {
		if (!vm) return;
		const doc = await vm.generate(recordingId);
		if (!doc) return;
		// The doc is created private (no teamspace) — surface it under Private
		// immediately instead of waiting for a reload.
		documentTree.addRoot(doc);
		meetingNotesModal.close();
		await goto(`/w/${workspaceId}/d/${doc.id}`);
	}
</script>

<svelte:window onkeydown={onKeydown} />

<!-- Backdrop: click to dismiss. -->
<div
	class="backdrop"
	role="button"
	tabindex="-1"
	aria-label="Close meeting notes"
	data-testid="meeting-notes-backdrop"
	onclick={() => meetingNotesModal.close()}
	onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && meetingNotesModal.close()}
></div>

<div
	class="panel"
	role="dialog"
	aria-modal="true"
	tabindex="-1"
	aria-label="Meeting notes"
	data-testid="meeting-notes-modal"
>
	<header class="head">
		<div>
			<h1>Meeting notes</h1>
			<p class="sub">Turn a recording into a structured document.</p>
		</div>
		<button
			class="close"
			aria-label="Close meeting notes"
			data-testid="meeting-notes-close"
			onclick={() => meetingNotesModal.close()}>×</button
		>
	</header>

	<div class="body" data-testid="meeting-notes-list">
		{#if vm}
			{#if vm.loading}
				<p class="muted" data-testid="meeting-notes-loading">Loading recordings…</p>
			{:else if vm.error}
				<p class="error" role="alert" data-testid="meeting-notes-error">{vm.error}</p>
			{:else if vm.recordings.length === 0}
				<p class="muted" data-testid="meeting-notes-empty">
					No meeting recordings yet.
				</p>
			{:else}
				{#each vm.groups as group (group.key)}
					{@const open = !vm.isCollapsed(group.key)}
					<section class="group" data-testid="meeting-month-group">
						<button
							type="button"
							class="month"
							class:open
							data-testid="meeting-month-toggle"
							aria-expanded={open}
							onclick={() => vm?.toggleMonth(group.key)}
						>
							<svg class="chev" viewBox="0 0 16 16" width="12" height="12" aria-hidden="true">
								<path
									d="M6 4l4 4-4 4"
									fill="none"
									stroke="currentColor"
									stroke-width="1.75"
									stroke-linecap="round"
									stroke-linejoin="round"
								/>
							</svg>
							<span class="month-label" data-testid="meeting-month-label">{monthLabel(group)}</span>
							<span class="count">{group.recordings.length}</span>
						</button>
						{#if open}
							<div class="recs">
								{#each group.recordings as recording (recording.id)}
									<div class="rec" data-testid="meeting-recording">
										<div class="rec-info">
											<span class="rec-title">{recording.headline || 'Untitled recording'}</span>
											<span class="rec-meta">
												{#if recording.captured_at}
													<span class="when">{shortWhen(recording.captured_at)}</span>
												{/if}
												<span
													class="status"
													class:ready={isReady(recording.status)}
													data-testid="meeting-status">{recording.status}</span
												>
											</span>
										</div>
										<button
											class="btn btn-primary"
											data-testid="meeting-generate"
											disabled={vm.pendingId !== null}
											onclick={() => generate(recording.id)}
										>
											{vm.pendingId === recording.id ? 'Generating…' : 'Generate document'}
										</button>
									</div>
								{/each}
							</div>
						{/if}
					</section>
				{/each}
			{/if}
		{/if}
	</div>
</div>

<style>
	.backdrop {
		position: fixed;
		inset: 0;
		z-index: 900;
		background: rgba(15, 15, 20, 0.35);
		backdrop-filter: blur(6px);
		-webkit-backdrop-filter: blur(6px);
		animation: fade 0.14s ease;
	}
	.panel {
		position: fixed;
		z-index: 901;
		top: 50%;
		left: 50%;
		transform: translate(-50%, -50%);
		width: min(520px, 94vw);
		max-height: 80vh;
		display: flex;
		flex-direction: column;
		background: var(--bg1);
		border: 1px solid var(--line);
		border-radius: var(--r-dialog);
		box-shadow: var(--sh2);
		animation: pop 0.16s cubic-bezier(0.2, 0.8, 0.3, 1);
	}
	@keyframes fade {
		from {
			opacity: 0;
		}
	}
	@keyframes pop {
		from {
			transform: translate(-50%, -48%);
			opacity: 0;
		}
	}
	.head {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 12px;
		padding: 18px 20px 12px;
		border-bottom: 1px solid var(--line);
	}
	.head h1 {
		margin: 0;
		font-size: 16px;
	}
	.sub {
		margin: 4px 0 0;
		font-size: 12px;
		color: var(--tx3);
	}
	.close {
		width: 28px;
		height: 28px;
		border: none;
		background: none;
		font-size: 22px;
		line-height: 1;
		color: var(--tx3);
		cursor: pointer;
		border-radius: var(--r-control);
	}
	.close:hover {
		background: var(--bg2);
		color: var(--tx);
	}
	.body {
		flex: 1;
		min-height: 0;
		overflow-y: auto;
		overscroll-behavior: contain;
		padding: 0 20px 18px;
	}
	.group {
		display: flex;
		flex-direction: column;
	}
	.recs {
		display: flex;
		flex-direction: column;
		gap: 6px;
		padding-top: 2px;
	}
	.month {
		position: sticky;
		top: 0;
		z-index: 1;
		display: flex;
		align-items: center;
		gap: 8px;
		width: 100%;
		margin: 0;
		padding: 13px 0 7px;
		border: none;
		background: var(--bg1);
		font-size: 11px;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--tx3);
		cursor: pointer;
		text-align: left;
	}
	.month:hover {
		color: var(--tx);
	}
	.month:focus-visible {
		outline: 2px solid var(--acc, #a9741f);
		outline-offset: 2px;
		border-radius: 4px;
	}
	.chev {
		flex: none;
		color: var(--tx3);
		transition: transform 0.15s ease;
	}
	.month.open .chev {
		transform: rotate(90deg);
	}
	.month-label {
		flex: 1;
	}
	.count {
		font-weight: 600;
		font-size: 11px;
		color: var(--tx3);
		background: var(--bg2);
		border-radius: 999px;
		padding: 1px 8px;
		letter-spacing: 0;
		font-variant-numeric: tabular-nums;
	}
	.rec {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
		padding: 9px 12px;
		border: 1px solid var(--line);
		border-radius: var(--r-control);
		background: var(--bg0);
		transition: border-color 0.12s ease;
	}
	.rec:hover {
		border-color: var(--tx3);
	}
	.rec-info {
		display: flex;
		flex-direction: column;
		gap: 4px;
		min-width: 0;
	}
	.rec-title {
		font-weight: 500;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.rec-meta {
		display: flex;
		align-items: center;
		gap: 8px;
		font-size: 12px;
		color: var(--tx3);
	}
	.when {
		font-variant-numeric: tabular-nums;
	}
	.status {
		display: inline-flex;
		align-items: center;
		gap: 5px;
		padding: 1px 8px;
		border-radius: 999px;
		font-size: 11px;
		font-weight: 500;
		text-transform: capitalize;
		color: var(--tx3);
		background: var(--bg2);
	}
	.status::before {
		content: '';
		width: 5px;
		height: 5px;
		border-radius: 50%;
		background: var(--tx3);
	}
	.status.ready {
		color: color-mix(in oklab, var(--ok, #3f8f5f) 82%, var(--tx));
		background: color-mix(in oklab, var(--ok, #3f8f5f) 16%, transparent);
	}
	.status.ready::before {
		background: var(--ok, #3f8f5f);
	}
	@media (prefers-reduced-motion: reduce) {
		.chev {
			transition: none;
		}
	}
	.btn.btn-primary:disabled {
		opacity: 0.5;
		cursor: default;
	}
	.muted {
		color: var(--tx3);
		font-size: 13px;
	}
	.error {
		color: var(--rose);
		font-size: 13px;
	}
</style>
