<script lang="ts">
	/** Notifications bell + inbox dropdown (mentions-and-notifications). Shows an
	 * unread badge (polled) and, when opened, the inbox; clicking a notification
	 * opens its document and marks it read. */
	import { goto } from '$app/navigation';
	import { notifications } from '$lib/viewmodels/notifications.svelte';

	let {
		workspaceId,
		variant = 'bell'
	}: { workspaceId: string; variant?: 'bell' | 'nav' } = $props();

	let open = $state(false);

	// Poll the unread count while mounted.
	$effect(() => {
		void notifications.refreshUnread();
		const id = setInterval(() => notifications.refreshUnread(), 30_000);
		return () => clearInterval(id);
	});

	async function toggle(): Promise<void> {
		open = !open;
		if (open) await notifications.load();
	}

	async function openNotification(n: {
		id: string;
		document_id: string | null;
	}): Promise<void> {
		await notifications.markRead(n.id);
		open = false;
		if (n.document_id) await goto(`/w/${workspaceId}/d/${n.document_id}`);
	}

	function timeAgo(iso: string): string {
		const s = Math.max(1, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
		if (s < 60) return `${s}s`;
		if (s < 3600) return `${Math.floor(s / 60)}m`;
		if (s < 86400) return `${Math.floor(s / 3600)}h`;
		return `${Math.floor(s / 86400)}d`;
	}
</script>

<div class="wrap" class:nav={variant === 'nav'}>
	{#if variant === 'nav'}
		<button
			class="nav-row"
			class:has-unread={notifications.unread > 0}
			data-testid="notifications-bell"
			aria-label="Notifications"
			title="Notifications"
			onclick={toggle}
		>
			<span aria-hidden="true">🔔</span> Notifications
			{#if notifications.unread > 0}
				<span class="count" data-testid="notifications-badge">{notifications.unread > 9 ? '9+' : notifications.unread}</span>
			{/if}
		</button>
	{:else}
		<button
			class="bell"
			class:has-unread={notifications.unread > 0}
			data-testid="notifications-bell"
			aria-label="Notifications"
			title="Notifications"
			onclick={toggle}
		>
			🔔
			{#if notifications.unread > 0}
				<span class="badge" data-testid="notifications-badge">{notifications.unread > 9 ? '9+' : notifications.unread}</span>
			{/if}
		</button>
	{/if}

	{#if open}
		<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
		<div class="scrim" role="presentation" onclick={() => (open = false)}></div>
		<div class="pop" class:pop-down={variant === 'nav'} data-testid="notifications-pop">
			<header>
				<strong>Notifications</strong>
				{#if notifications.items.some((n) => !n.read)}
					<button class="link" data-testid="notifications-mark-all" onclick={() => notifications.markAll()}>Mark all read</button>
				{/if}
			</header>
			<div class="list">
				{#if notifications.loading}
					<p class="empty">Loading…</p>
				{:else if notifications.items.length === 0}
					<p class="empty">You're all caught up.</p>
				{:else}
					{#each notifications.items as n (n.id)}
						<button class="item" class:unread={!n.read} data-testid="notification" onclick={() => openNotification(n)}>
							<span class="dot" class:on={!n.read}></span>
							<span class="text">
								<span class="line"><b>{n.actor_id.slice(0, 8)}</b> mentioned you</span>
								{#if n.snippet}<span class="snippet">{n.snippet}</span>{/if}
							</span>
							<span class="age">{timeAgo(n.created_at)}</span>
						</button>
					{/each}
				{/if}
			</div>
		</div>
	{/if}
</div>

<style>
	.wrap {
		position: relative;
	}
	.bell {
		position: relative;
		width: 100%;
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 6px 10px;
		border-radius: var(--r-control);
		color: var(--tx2);
		font-size: 13px;
	}
	.bell:hover {
		background: var(--bg2);
		color: var(--tx);
	}
	/* nav-row variant: matches the sidebar's top-nav buttons (.chat-btn). */
	.nav-row {
		display: flex;
		align-items: center;
		gap: 6px;
		width: 100%;
		padding: 6px 8px;
		margin-bottom: 4px;
		border-radius: var(--r-control);
		color: var(--tx2);
		font-weight: 500;
		text-align: left;
	}
	.nav-row:hover {
		background: var(--bg2);
		color: var(--tx);
	}
	.count {
		margin-left: auto;
		min-width: 17px;
		height: 17px;
		padding: 0 5px;
		display: grid;
		place-items: center;
		border-radius: var(--r-pill);
		background: var(--acc);
		color: #fff;
		font-size: 10px;
		font-weight: 700;
	}
	.badge {
		position: absolute;
		left: 20px;
		top: 3px;
		min-width: 15px;
		height: 15px;
		padding: 0 3px;
		display: grid;
		place-items: center;
		border-radius: 8px;
		background: var(--rose, #e11d48);
		color: #fff;
		font-size: 9.5px;
		font-weight: 700;
	}
	.scrim {
		position: fixed;
		inset: 0;
		z-index: 60;
	}
	.pop {
		position: absolute;
		bottom: calc(100% + 6px);
		left: 0;
		z-index: 61;
		width: 320px;
		max-width: 88vw;
		background: var(--bg1);
		border: 1px solid var(--line);
		border-radius: 12px;
		box-shadow: var(--sh3);
		overflow: hidden;
	}
	/* When triggered from the top nav, open downward instead of upward. */
	.pop.pop-down {
		bottom: auto;
		top: calc(100% + 6px);
	}
	header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 10px 12px;
		border-bottom: 1px solid var(--line);
		font-size: 13px;
		color: var(--tx);
	}
	.link {
		color: var(--acc);
		font-size: 12px;
	}
	.list {
		max-height: 340px;
		overflow-y: auto;
	}
	.item {
		width: 100%;
		display: flex;
		gap: 8px;
		align-items: flex-start;
		padding: 9px 12px;
		text-align: left;
		border-bottom: 1px solid var(--line);
	}
	.item:hover {
		background: var(--bg2);
	}
	.item.unread {
		background: var(--aibg, var(--accbg));
	}
	.dot {
		width: 7px;
		height: 7px;
		margin-top: 5px;
		border-radius: 50%;
		flex-shrink: 0;
		background: transparent;
	}
	.dot.on {
		background: var(--acc);
	}
	.text {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: 2px;
	}
	.line {
		font-size: 12.5px;
		color: var(--tx);
	}
	.snippet {
		font-size: 12px;
		color: var(--tx2);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.age {
		font-size: 11px;
		color: var(--tx3);
		flex-shrink: 0;
	}
	.empty {
		margin: 0;
		padding: 20px 12px;
		text-align: center;
		font-size: 12.5px;
		color: var(--tx3);
	}
</style>
