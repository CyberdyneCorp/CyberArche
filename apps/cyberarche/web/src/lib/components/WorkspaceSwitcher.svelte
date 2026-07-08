<script lang="ts">
	import { goto } from '$app/navigation';
	import { workspaces } from '$lib/viewmodels/workspaces.svelte';

	let { workspaceId }: { workspaceId: string } = $props();

	let open = $state(false);
	let creating = $state(false);
	let newName = $state('');

	const current = $derived(workspaces.byId(workspaceId));
	const initials = $derived(
		(current?.name ?? 'CA')
			.split(/\s+/)
			.map((part) => part[0])
			.join('')
			.slice(0, 2)
			.toUpperCase()
	);

	async function switchTo(id: string) {
		open = false;
		await goto(`/w/${id}`);
	}

	async function create(event: SubmitEvent) {
		event.preventDefault();
		const name = newName.trim();
		if (!name) return;
		const workspace = await workspaces.create(name);
		newName = '';
		creating = false;
		open = false;
		await goto(`/w/${workspace.id}`);
	}
</script>

<svelte:window onkeydown={(event) => event.key === 'Escape' && (open = false)} />

<div class="switcher">
	<button
		class="current"
		aria-haspopup="menu"
		aria-expanded={open}
		data-testid="workspace-switcher"
		onclick={() => (open = !open)}
	>
		<span class="mark">{initials}</span>
		<span class="meta">
			<strong data-testid="workspace-name">{current?.name ?? '…'}</strong>
			<span class="sub">Current workspace</span>
		</span>
		<span class="chev">⌄</span>
	</button>

	{#if open}
		<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
		<div class="scrim" onclick={() => (open = false)}></div>
		<div class="menu" role="menu" data-testid="workspace-menu">
			{#each workspaces.items as workspace (workspace.id)}
				<button
					role="menuitem"
					class="item"
					class:active={workspace.id === workspaceId}
					data-testid="workspace-option"
					onclick={() => switchTo(workspace.id)}
				>
					<span class="dot"></span>
					<span class="name">{workspace.name}</span>
					{#if workspace.id === workspaceId}<span class="tick">✓</span>{/if}
				</button>
			{/each}

			<div class="sep"></div>

			{#if creating}
				<form class="create" onsubmit={create}>
					<!-- svelte-ignore a11y_autofocus -->
					<input
						class="input"
						placeholder="Workspace name"
						bind:value={newName}
						autofocus
						data-testid="new-workspace-name"
					/>
					<button class="btn btn-primary" type="submit" data-testid="new-workspace-create"
						>Create</button
					>
				</form>
			{:else}
				<button
					role="menuitem"
					class="item"
					data-testid="new-workspace"
					onclick={() => (creating = true)}>＋ New workspace</button
				>
			{/if}
			<a class="item" role="menuitem" href={`/w/${workspaceId}/settings`}
				>⚙ Workspace settings</a
			>
		</div>
	{/if}
</div>

<style>
	.switcher {
		position: relative;
	}
	.current {
		display: flex;
		align-items: center;
		gap: 8px;
		width: 100%;
		padding: 6px;
		border-radius: var(--r-control);
		text-align: left;
	}
	.current:hover {
		background: var(--bg2);
	}
	.mark {
		display: grid;
		place-items: center;
		width: 26px;
		height: 26px;
		min-width: 26px;
		border-radius: 7px;
		background: var(--tx);
		color: var(--bg1);
		font-size: 10.5px;
		font-weight: 700;
	}
	.meta {
		display: flex;
		flex-direction: column;
		min-width: 0;
		flex: 1;
	}
	.meta strong {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.sub {
		color: var(--tx3);
		font-size: 10px;
	}
	.chev {
		color: var(--tx3);
		font-size: 11px;
	}
	.scrim {
		position: fixed;
		inset: 0;
		z-index: 40;
	}
	.menu {
		position: absolute;
		z-index: 50;
		top: calc(100% + 4px);
		left: 0;
		width: 240px;
		background: var(--bg1);
		border: 1px solid var(--line);
		border-radius: var(--r-block);
		box-shadow: var(--sh2);
		padding: 4px;
		animation: rise 120ms ease-out;
	}
	@keyframes rise {
		from {
			opacity: 0;
			transform: translateY(4px);
		}
	}
	.item {
		display: flex;
		align-items: center;
		gap: 8px;
		width: 100%;
		padding: 6px 8px;
		border-radius: var(--r-control);
		text-align: left;
		color: var(--tx);
		text-decoration: none;
	}
	.item:hover {
		background: var(--bg2);
	}
	.item.active {
		background: var(--accbg);
	}
	.dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--acc);
	}
	.name {
		flex: 1;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.tick {
		color: var(--acc-strong);
	}
	.sep {
		height: 1px;
		background: var(--line);
		margin: 4px 0;
	}
	.create {
		display: flex;
		gap: 4px;
		padding: 4px;
	}
	.create .input {
		flex: 1;
		min-width: 0;
	}
</style>
