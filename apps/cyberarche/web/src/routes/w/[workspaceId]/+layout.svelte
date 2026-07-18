<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import CommandPalette from '$lib/components/CommandPalette.svelte';
	import GraphModal from '$lib/components/GraphModal.svelte';
	import MeetingNotesModal from '$lib/components/MeetingNotesModal.svelte';
	import SettingsModal from '$lib/components/SettingsModal.svelte';
	import Sidebar from '$lib/components/Sidebar.svelte';
	import WorkspaceChat from '$lib/components/WorkspaceChat.svelte';
	import { documentTree } from '$lib/viewmodels/document-tree.svelte';
	import { linkIndex } from '$lib/viewmodels/link-index.svelte';
	import { commandPalette } from '$lib/viewmodels/commandPalette.svelte';
	import { session } from '$lib/viewmodels/session.svelte';
	import { settingsModal } from '$lib/viewmodels/settingsModal.svelte';
	import { workspaceChatOpen } from '$lib/viewmodels/workspaceChat.svelte';
	import { meetingNotesModal } from '$lib/viewmodels/meetingNotesModal.svelte';
	import { createTeamspaces, type TeamspacesVM } from '$lib/viewmodels/teamspaces.svelte';
	import { workspaces } from '$lib/viewmodels/workspaces.svelte';

	let { children } = $props();
	const workspaceId = $derived(page.params.workspaceId!);

	let teamspaces = $state<TeamspacesVM | null>(null);

	$effect(() => {
		if (session.restoring) return; // wait for the cookie-based restore to settle
		if (!session.isAuthenticated) {
			goto('/signin');
			return;
		}
		(async () => {
			if (!workspaces.loaded) await workspaces.load();
			if (workspaceId === 'new') return;
			if (documentTree.workspaceId !== workspaceId) {
				await documentTree.open(workspaceId);
			}
			// Index the workspace's documents for wikilink resolution + Cmd+K.
			linkIndex.load(workspaceId);
			const vm = createTeamspaces(workspaceId);
			teamspaces = vm;
			await vm.load();
		})();
	});

	function onWindowKeydown(event: KeyboardEvent) {
		if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
			event.preventDefault();
			commandPalette.toggle();
		}
	}
</script>

<svelte:window onkeydown={onWindowKeydown} />

{#if workspaceId === 'new'}
	<main class="first-run">
		<div class="card">
			<h1>Create your first workspace</h1>
			<form
				onsubmit={async (event) => {
					event.preventDefault();
					const input = (event.currentTarget as HTMLFormElement).elements.namedItem(
						'name'
					) as HTMLInputElement;
					const workspace = await workspaces.create(input.value || 'My Workspace');
					await goto(`/w/${workspace.id}`);
				}}
			>
				<input class="input" name="name" placeholder="Workspace name" data-testid="workspace-name-input" />
				<button class="btn btn-primary" type="submit" data-testid="create-workspace">Create</button>
			</form>
		</div>
	</main>
{:else}
	<div class="shell">
		<Sidebar {workspaceId} {teamspaces} />
		<main class="content">
			{@render children()}
		</main>
	</div>
	{#if commandPalette.isOpen}
		<CommandPalette {workspaceId} onclose={() => commandPalette.close()} />
	{/if}
	<GraphModal {workspaceId} />
	{#if settingsModal.isOpen}
		<SettingsModal {workspaceId} />
	{/if}
	{#if workspaceChatOpen.isOpen}
		<WorkspaceChat {workspaceId} />
	{/if}
	{#if meetingNotesModal.isOpen}
		<MeetingNotesModal {workspaceId} />
	{/if}
{/if}

<style>
	.shell {
		display: flex;
		height: 100vh;
		overflow: hidden;
	}
	.content {
		flex: 1;
		background: var(--bg1);
		overflow: hidden; /* document + agent panel manage their own scroll */
		min-width: 0;
	}
	.first-run {
		display: grid;
		place-items: center;
		height: 100vh;
	}
	.card {
		background: var(--bg1);
		border: 1px solid var(--line);
		border-radius: var(--r-dialog);
		box-shadow: var(--sh2);
		padding: 28px;
		width: 380px;
	}
	.card h1 {
		margin: 0 0 14px;
		font-size: 20px;
	}
	.card form {
		display: flex;
		gap: 8px;
	}
	.card input {
		flex: 1;
	}
</style>
