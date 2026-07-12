<script lang="ts">
	export interface MenuItem {
		/** Omitted only for separators. */
		label?: string;
		danger?: boolean;
		testid?: string;
		/** A section label (non-clickable) when true. */
		heading?: boolean;
		/** A thin divider between groups when true; other fields ignored. */
		separator?: boolean;
		/** Marks the currently-active choice (e.g. the current heading level). */
		active?: boolean;
		/** An emoji/glyph shown before the label. */
		icon?: string;
		onSelect?: () => void;
	}

	let {
		x,
		y,
		items,
		onclose
	}: { x: number; y: number; items: MenuItem[]; onclose: () => void } = $props();
</script>

<svelte:window onkeydown={(e) => e.key === 'Escape' && onclose()} />

<!-- Full-screen scrim closes the menu on any outside click / right-click. -->
<div
	class="scrim"
	role="presentation"
	onclick={onclose}
	oncontextmenu={(e) => {
		e.preventDefault();
		onclose();
	}}
></div>

<div class="menu" role="menu" data-testid="context-menu" style="left: {x}px; top: {y}px;">
	{#each items as item, i (i)}
		{#if item.separator}
			<div class="sep" role="separator"></div>
		{:else if item.heading}
			<div class="heading">{item.label}</div>
		{:else}
			<!-- mousedown (not click) so the editable keeps its selection/focus when
			     a formatting action needs it; preventDefault stops the blur. -->
			<button
				class="item"
				class:danger={item.danger}
				class:active={item.active}
				role="menuitem"
				data-testid={item.testid}
				onmousedown={(e) => {
					e.preventDefault();
					item.onSelect?.();
					onclose();
				}}
			>
				{#if item.icon}<span class="icon">{item.icon}</span>{/if}
				<span class="label">{item.label}</span>
				{#if item.active}<span class="check">✓</span>{/if}
			</button>
		{/if}
	{/each}
</div>

<style>
	.scrim {
		position: fixed;
		inset: 0;
		z-index: 1200;
	}
	.menu {
		position: fixed;
		z-index: 1201;
		min-width: 150px;
		padding: 4px;
		background: var(--bg1, #fff);
		border: 1px solid var(--line, #e5e7eb);
		border-radius: 10px;
		box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
		display: flex;
		flex-direction: column;
	}
	.item {
		display: flex;
		align-items: center;
		gap: 8px;
		text-align: left;
		padding: 7px 10px;
		border-radius: 6px;
		font-size: 13px;
		color: var(--tx, #111);
	}
	.item:hover {
		background: var(--bg2, #f3f4f6);
	}
	.item .label {
		flex: 1;
	}
	.item .icon {
		width: 16px;
		text-align: center;
		color: var(--tx2);
	}
	.item.active {
		color: var(--acc-strong);
	}
	.item .check {
		color: var(--acc-strong);
		font-size: 11px;
	}
	.heading {
		padding: 6px 10px 3px;
		font-size: 10.5px;
		font-weight: 600;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: var(--tx3);
	}
	.sep {
		height: 1px;
		margin: 4px 6px;
		background: var(--line);
	}
	.item.danger {
		color: var(--rose, #e11d48);
	}
	.item.danger:hover {
		background: color-mix(in srgb, var(--rose, #e11d48) 12%, transparent);
	}
</style>
