<script lang="ts">
	import type { CollectionRow } from '$lib/api/collections';

	let {
		date,
		inMonth,
		isToday,
		rows,
		onOpenRow
	}: {
		date: Date;
		/** Whether this day belongs to the anchored month (vs. a leading/trailing spill day). */
		inMonth: boolean;
		isToday: boolean;
		/** Rows falling on this day, in filtered/sorted order. */
		rows: CollectionRow[];
		onOpenRow: (rowId: string) => void;
	} = $props();
</script>

<div class="cell" class:dim={!inMonth} class:today={isToday} data-testid="calendar-day">
	<span class="daynum" data-testid="calendar-daynum">{date.getDate()}</span>
	<div class="chips">
		{#each rows as row (row.id)}
			<button
				class="chip"
				data-testid="calendar-chip"
				title={row.title}
				onclick={() => onOpenRow(row.id)}
			>
				{row.title || 'Untitled'}
			</button>
		{/each}
	</div>
</div>

<style>
	.cell {
		display: flex;
		flex-direction: column;
		gap: 4px;
		min-height: 92px;
		padding: 4px;
		border: 1px solid var(--line);
		background: var(--bg1, #fff);
	}
	.cell.dim {
		background: var(--bg0);
	}
	.cell.dim .daynum {
		color: var(--tx3);
	}
	.daynum {
		font-size: 12px;
		color: var(--tx2);
		align-self: flex-end;
	}
	.cell.today .daynum {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-width: 20px;
		height: 20px;
		border-radius: 50%;
		background: var(--acc);
		color: #fff;
		font-weight: 600;
	}
	.chips {
		display: flex;
		flex-direction: column;
		gap: 3px;
	}
	.chip {
		text-align: left;
		font-size: 12px;
		padding: 2px 6px;
		border-radius: 4px;
		background: var(--accbg);
		color: var(--acc-strong);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.chip:hover {
		filter: brightness(0.95);
	}
</style>
