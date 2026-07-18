<script lang="ts">
	import type { PathCrumb } from '$lib/api/documents';

	let {
		crumbs,
		workspaceId,
		onNavigate
	}: {
		crumbs: PathCrumb[];
		workspaceId: string;
		/** Called with the SPA path to navigate to when a link crumb is clicked. */
		onNavigate: (path: string) => void;
	} = $props();

	/** The navigation target for a crumb, or null when it is plain context text
	 * (teamspace/folder, or the final crumb — the current document). */
	function targetFor(crumb: PathCrumb, index: number): string | null {
		if (index === crumbs.length - 1) return null;
		if (crumb.kind === 'workspace') return `/w/${workspaceId}`;
		if (crumb.kind === 'document') return `/w/${workspaceId}/d/${crumb.id}`;
		return null;
	}
</script>

<nav class="crumbs" aria-label="Breadcrumb" data-testid="breadcrumb">
	{#each crumbs as crumb, index (crumb.kind + ':' + crumb.id + ':' + index)}
		{#if index > 0}
			<span class="sep" aria-hidden="true">›</span>
		{/if}
		{@const target = targetFor(crumb, index)}
		{#if target}
			<a
				class="crumb link"
				href={target}
				data-testid="crumb-link"
				onclick={(event) => {
					event.preventDefault();
					onNavigate(target);
				}}>{crumb.label}</a
			>
		{:else}
			<span class="crumb" data-testid="crumb-text" data-kind={crumb.kind}>{crumb.label}</span>
		{/if}
	{/each}
</nav>

<style>
	.crumbs {
		display: flex;
		align-items: center;
		gap: 6px;
		min-width: 0;
		overflow: hidden;
		color: var(--tx2);
		font-size: 13px;
	}
	.crumb {
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		max-width: 22ch;
	}
	.link {
		color: var(--tx2);
		cursor: pointer;
		background: none;
		border: none;
		padding: 0;
		text-decoration: none;
	}
	.link:hover {
		color: var(--tx);
		text-decoration: underline;
	}
	.crumb[data-testid='crumb-text']:last-child {
		color: var(--tx);
		font-weight: 600;
	}
	.sep {
		color: var(--tx3);
		flex: none;
	}
</style>
