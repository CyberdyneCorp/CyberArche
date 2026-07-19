<script lang="ts">
	/** Org-user combobox (org-directory spec): search the directory by email and
	 * pick a user as the invite target. Falls back to raw-id entry when the
	 * directory is unavailable — or on demand for org users who know the id. */
	import type { OrgUser } from '$lib/api/orgUsers';
	import type { OrgUsersVM } from '$lib/viewmodels/orgUsers.svelte';

	let {
		orgUsers,
		testid,
		onselect
	}: {
		orgUsers: OrgUsersVM;
		testid: string;
		onselect: (userId: string | null) => void;
	} = $props();

	let query = $state('');
	let rawId = $state('');
	let open = $state(false);
	let highlighted = $state(0);
	let wantsManual = $state(false);

	const manual = $derived(wantsManual || orgUsers.unavailable);

	function labelOf(user: OrgUser): string {
		return user.email ?? user.id;
	}

	function initialOf(user: OrgUser): string {
		return labelOf(user).charAt(0).toUpperCase();
	}

	function pick(user: OrgUser) {
		query = labelOf(user);
		open = false;
		onselect(user.id);
	}

	function onInput() {
		open = true;
		highlighted = 0;
		onselect(null);
		orgUsers.search(query);
	}

	function moveHighlight(delta: number) {
		const count = orgUsers.users.length;
		if (count > 0) highlighted = (highlighted + delta + count) % count;
	}

	function onKeydown(event: KeyboardEvent) {
		if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
			event.preventDefault();
			open = true;
			moveHighlight(event.key === 'ArrowDown' ? 1 : -1);
		} else if (event.key === 'Enter' && open && orgUsers.users[highlighted]) {
			event.preventDefault();
			pick(orgUsers.users[highlighted]);
		} else if (event.key === 'Escape' && open) {
			event.stopPropagation();
			open = false;
		}
	}

	function setManual(value: boolean) {
		wantsManual = value;
		open = false;
		onselect(value ? rawId.trim() || null : null);
	}

	// Blur fires before the option's click — delay so the pick still lands.
	function onBlur() {
		setTimeout(() => (open = false), 150);
	}

	/** Reset both inputs (e.g. after a successful invite). */
	export function clear() {
		query = '';
		rawId = '';
		open = false;
		onselect(null);
	}
</script>

{#if manual}
	<div class="picker">
		<input
			class="input grow"
			placeholder="User id (Cyberdyne identity)"
			bind:value={rawId}
			oninput={() => onselect(rawId.trim() || null)}
			data-testid={testid}
		/>
		{#if !orgUsers.unavailable}
			<button type="button" class="mode" data-testid="{testid}-search-directory" onclick={() => setManual(false)}>
				Search the directory instead
			</button>
		{/if}
	</div>
{:else}
	<div class="picker">
		<input
			class="input grow"
			role="combobox"
			aria-expanded={open}
			aria-controls="{testid}-results"
			aria-autocomplete="list"
			autocomplete="off"
			placeholder="Search people by email…"
			bind:value={query}
			oninput={onInput}
			onfocus={() => (open = true)}
			onblur={onBlur}
			onkeydown={onKeydown}
			data-testid={testid}
		/>
		{#if open}
			<div class="menu" role="listbox" id="{testid}-results" data-testid="{testid}-results">
				{#if orgUsers.loading}
					<p class="note">Searching…</p>
				{:else}
					{#each orgUsers.users as user, index (user.id)}
						<button
							type="button"
							class="option"
							class:highlighted={index === highlighted}
							class:inactive={!user.is_active}
							role="option"
							aria-selected={index === highlighted}
							data-testid="{testid}-option"
							onpointerenter={() => (highlighted = index)}
							onclick={() => pick(user)}
						>
							{#if user.avatar_url}
								<img class="avatar" src={user.avatar_url} alt="" />
							{:else}
								<span class="avatar fallback" aria-hidden="true">{initialOf(user)}</span>
							{/if}
							<span class="label">{labelOf(user)}</span>
							{#if !user.is_active}
								<span class="chip">inactive</span>
							{/if}
						</button>
					{:else}
						<p class="note">No matching people.</p>
					{/each}
				{/if}
			</div>
		{/if}
		<button type="button" class="mode" data-testid="{testid}-manual" onclick={() => setManual(true)}>
			Enter user id manually
		</button>
	</div>
{/if}

<style>
	.picker {
		position: relative;
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 4px;
		min-width: 0;
	}
	.grow {
		width: 100%;
	}
	.menu {
		position: absolute;
		top: calc(100% + 4px);
		left: 0;
		right: 0;
		z-index: 5;
		max-height: 220px;
		overflow-y: auto;
		background: var(--bg1);
		border: 1px solid var(--line);
		border-radius: var(--r-control);
		box-shadow: var(--sh3);
		padding: 4px;
	}
	.option {
		display: flex;
		align-items: center;
		gap: 8px;
		width: 100%;
		padding: 6px 8px;
		border-radius: var(--r-control);
		text-align: left;
		font-size: 12.5px;
		color: var(--tx);
	}
	.option.highlighted {
		background: var(--bg3);
	}
	.option.inactive {
		opacity: 0.55;
	}
	.avatar {
		width: 22px;
		height: 22px;
		border-radius: 50%;
		object-fit: cover;
		flex: 0 0 auto;
	}
	.avatar.fallback {
		display: grid;
		place-items: center;
		background: var(--accbg);
		color: var(--acc-strong);
		font-size: 11px;
		font-weight: 600;
	}
	.label {
		flex: 1;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.chip {
		font-size: 10.5px;
		color: var(--tx3);
	}
	.note {
		margin: 6px 8px;
		font-size: 12px;
		color: var(--tx3);
	}
	.mode {
		align-self: flex-start;
		font-size: 11px;
		color: var(--acc-strong);
	}
</style>
