<script lang="ts">
	/** Manage a teamspace's members (teamspace-export-and-members): invite a user
	 * by CyberdyneAuth id with a role, list members, remove them. The backend
	 * endpoints already exist; this is the UI. */
	import {
		addTeamspaceMember,
		removeTeamspaceMember,
		teamspaceMembers,
		type TeamspaceMember
	} from '$lib/api/teamspaces';
	import type { ShareRole } from '$lib/api/sharing';
	import { toasts } from '$lib/viewmodels/toasts.svelte';

	let {
		teamspaceId,
		teamspaceName,
		onclose
	}: { teamspaceId: string; teamspaceName: string; onclose: () => void } = $props();

	let members = $state<TeamspaceMember[]>([]);
	let inviteId = $state('');
	let inviteRole = $state<ShareRole>('editor');
	let busy = $state(false);

	async function refresh(): Promise<void> {
		try {
			members = await teamspaceMembers(teamspaceId);
		} catch {
			toasts.error("Couldn't load members");
		}
	}
	$effect(() => {
		void refresh();
	});

	async function invite(): Promise<void> {
		const id = inviteId.trim();
		if (!id || busy) return;
		busy = true;
		try {
			await addTeamspaceMember(teamspaceId, id, inviteRole);
			inviteId = '';
			toasts.success('Member invited');
			await refresh();
		} catch {
			toasts.error("Couldn't invite that user (owners only)");
		} finally {
			busy = false;
		}
	}
	async function remove(userId: string): Promise<void> {
		try {
			await removeTeamspaceMember(teamspaceId, userId);
			toasts.success('Member removed');
			await refresh();
		} catch {
			toasts.error("Couldn't remove that member");
		}
	}
</script>

<svelte:window onkeydown={(e) => e.key === 'Escape' && onclose()} />

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="backdrop" role="presentation" onclick={onclose}>
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div class="panel" role="dialog" aria-label="Teamspace members" tabindex="-1" onclick={(e) => e.stopPropagation()}>
		<header>
			<h2>Members — {teamspaceName}</h2>
			<button class="x" aria-label="Close" onclick={onclose}>✕</button>
		</header>

		<form
			class="invite"
			onsubmit={(e) => {
				e.preventDefault();
				void invite();
			}}
		>
			<input
				class="input"
				placeholder="User ID to invite…"
				bind:value={inviteId}
				data-testid="ts-invite-id"
			/>
			<select class="input role" bind:value={inviteRole} data-testid="ts-invite-role">
				<option value="editor">Editor</option>
				<option value="viewer">Viewer</option>
				<option value="owner">Owner</option>
			</select>
			<button class="btn" type="submit" disabled={busy} data-testid="ts-invite">Invite</button>
		</form>
		<p class="hint">Editors and owners can author documents in this teamspace.</p>

		<div class="list">
			{#each members as m (m.user_id)}
				<div class="member" data-testid="ts-member">
					<span class="who">{m.user_id}</span>
					<span class="role">{m.role}</span>
					{#if m.role !== 'owner'}
						<button class="rm" aria-label="Remove" onclick={() => remove(m.user_id)}>Remove</button>
					{/if}
				</div>
			{:else}
				<p class="empty">No members yet.</p>
			{/each}
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
		width: min(92vw, 440px);
		background: var(--bg2);
		border: 1px solid var(--line);
		border-radius: var(--r-block);
		box-shadow: var(--sh3);
		padding: 18px;
	}
	header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 14px;
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
	.invite {
		display: flex;
		gap: 6px;
	}
	.invite .input {
		flex: 1;
	}
	.role {
		flex: 0 0 auto;
		width: auto;
	}
	.btn {
		padding: 6px 12px;
		border-radius: var(--r-control);
		background: var(--acc);
		color: #fff;
		font-weight: 600;
		font-size: 13px;
	}
	.hint {
		margin: 8px 0 12px;
		font-size: 12px;
		color: var(--tx3);
	}
	.list {
		display: flex;
		flex-direction: column;
		gap: 4px;
		max-height: 280px;
		overflow-y: auto;
	}
	.member {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 8px 10px;
		border: 1px solid var(--line);
		border-radius: var(--r-control);
		background: var(--bg1);
	}
	.who {
		flex: 1;
		font-size: 12.5px;
		color: var(--tx);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.role {
		font-size: 11.5px;
		color: var(--tx2);
		text-transform: capitalize;
	}
	.rm {
		font-size: 12px;
		color: var(--rose);
		padding: 3px 8px;
		border-radius: var(--r-control);
	}
	.rm:hover {
		background: var(--bg3);
	}
	.empty {
		margin: 8px 0;
		font-size: 12.5px;
		color: var(--tx3);
		text-align: center;
	}
</style>
