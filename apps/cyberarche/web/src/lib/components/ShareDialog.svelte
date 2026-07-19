<script lang="ts">
	import type { SharePermission, ShareRole } from '$lib/api/sharing';
	import type { SharingVM } from '$lib/viewmodels/sharing.svelte';
	import { createOrgUsers } from '$lib/viewmodels/orgUsers.svelte';
	import OrgUserPicker from './OrgUserPicker.svelte';

	let { sharing, onclose }: { sharing: SharingVM; onclose: () => void } = $props();

	const orgUsers = createOrgUsers();
	$effect(() => {
		void orgUsers.load();
	});

	let picker = $state<OrgUserPicker | null>(null);
	let inviteTarget = $state<string | null>(null);
	let inviteRole = $state<ShareRole>('editor');
	let linkPermission = $state<SharePermission>('view');
	let copied = $state<string | null>(null);

	async function invite() {
		if (!inviteTarget) return;
		await sharing.invite(inviteTarget, inviteRole);
		if (sharing.invited) picker?.clear();
	}

	async function copy(url: string, id: string) {
		await navigator.clipboard.writeText(url);
		copied = id;
		setTimeout(() => (copied = null), 1500);
	}
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="backdrop" onclick={onclose}>
	<div
		class="dialog"
		role="dialog"
		aria-label="Share"
		data-testid="share-dialog"
		onclick={(event) => event.stopPropagation()}
	>
		<header>
			<h2>Share</h2>
			<button class="close" aria-label="Close" onclick={onclose}>✕</button>
		</header>

		<section>
			<h3>Invite</h3>
			<form
				class="row"
				onsubmit={async (event) => {
					event.preventDefault();
					await invite();
				}}
			>
				<OrgUserPicker
					bind:this={picker}
					{orgUsers}
					testid="invite-user"
					onselect={(userId) => (inviteTarget = userId)}
				/>
				<select class="input" bind:value={inviteRole} data-testid="invite-role">
					<option value="editor">Editor</option>
					<option value="commenter">Commenter</option>
					<option value="viewer">Viewer</option>
					<option value="owner">Owner</option>
				</select>
				<button class="btn btn-primary" type="submit" disabled={!inviteTarget}>Invite</button>
			</form>
			{#if sharing.invited}
				<p class="ok" data-testid="invite-ok">Invited {sharing.invited}</p>
			{/if}
		</section>

		<section>
			<h3>Anyone with the link</h3>
			<div class="row">
				<select class="input" bind:value={linkPermission} data-testid="link-permission">
					<option value="view">Can view</option>
					<option value="comment">Can comment</option>
					<option value="edit">Can edit</option>
				</select>
				<button
					class="btn btn-secondary"
					data-testid="create-link"
					onclick={() => sharing.createLink(linkPermission)}>Create link</button
				>
			</div>
			{#each sharing.links as link (link.id)}
				<div class="link-row" class:revoked={link.revoked} data-testid="share-link">
					<span class="chip">{link.permission}</span>
					<code class="url">{sharing.linkUrl(link)}</code>
					{#if link.revoked}
						<span class="chip">revoked</span>
					{:else}
						<button class="mini" onclick={() => copy(sharing.linkUrl(link), link.id)}>
							{copied === link.id ? 'Copied ✓' : 'Copy'}
						</button>
						<button
							class="mini danger"
							data-testid="revoke-link"
							onclick={() => sharing.revokeLink(link.id)}>Revoke</button
						>
					{/if}
				</div>
			{/each}
		</section>

		{#if sharing.error}
			<p class="error" role="alert">{sharing.error}</p>
		{/if}
	</div>
</div>

<style>
	.backdrop {
		position: fixed;
		inset: 0;
		background: rgba(20, 16, 10, 0.35);
		display: grid;
		place-items: center;
		z-index: 80;
	}
	.dialog {
		width: 460px;
		background: var(--bg1);
		border-radius: var(--r-dialog);
		box-shadow: var(--sh3);
		padding: 18px 20px;
	}
	header {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}
	h2 {
		margin: 0;
		font-size: 16px;
	}
	.close {
		color: var(--tx3);
	}
	section {
		margin-top: 14px;
	}
	h3 {
		margin: 0 0 8px;
		font-size: 10.5px;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--tx3);
	}
	.row {
		display: flex;
		align-items: flex-start;
		gap: 6px;
	}
	.ok {
		color: var(--ok);
		margin: 6px 0 0;
	}
	.link-row {
		display: flex;
		align-items: center;
		gap: 8px;
		margin-top: 8px;
	}
	.link-row.revoked {
		opacity: 0.55;
	}
	.url {
		flex: 1;
		font-size: 11px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		color: var(--tx2);
	}
	.mini {
		font-size: 11px;
		color: var(--acc-strong);
	}
	.mini.danger {
		color: var(--rose);
	}
	.error {
		color: var(--rose);
	}
</style>
