<script lang="ts">
	export interface MenuItem {
		label: string;
		danger?: boolean;
		testid?: string;
		onSelect: () => void;
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
	{#each items as item (item.label)}
		<button
			class="item"
			class:danger={item.danger}
			role="menuitem"
			data-testid={item.testid}
			onclick={() => {
				item.onSelect();
				onclose();
			}}>{item.label}</button
		>
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
		text-align: left;
		padding: 7px 10px;
		border-radius: 6px;
		font-size: 13px;
		color: var(--tx, #111);
	}
	.item:hover {
		background: var(--bg2, #f3f4f6);
	}
	.item.danger {
		color: var(--rose, #e11d48);
	}
	.item.danger:hover {
		background: color-mix(in srgb, var(--rose, #e11d48) 12%, transparent);
	}
</style>
