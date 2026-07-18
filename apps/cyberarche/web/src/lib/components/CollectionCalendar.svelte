<script lang="ts">
	import { dayKey, groupRowsByDay, monthGrid } from '$lib/viewmodels/calendar';
	import type { CollectionVM } from '$lib/viewmodels/collection.svelte';
	import CollectionCalendarDay from './CollectionCalendarDay.svelte';

	let {
		vm,
		onOpenRow
	}: {
		vm: CollectionVM;
		onOpenRow: (rowId: string) => void;
	} = $props();

	const MONTHS = [
		'January', 'February', 'March', 'April', 'May', 'June',
		'July', 'August', 'September', 'October', 'November', 'December'
	];
	const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

	const dateBy = $derived(vm.dateByProperty);

	// Component-local: the displayed month. Reads "today" once at init; the pure
	// grid/grouping helpers never touch the ambient clock.
	let anchor = $state(new Date());
	const todayKey = dayKey(new Date());

	const year = $derived(anchor.getFullYear());
	const month0 = $derived(anchor.getMonth());
	const weeks = $derived(monthGrid(year, month0));
	const grouping = $derived(dateBy ? groupRowsByDay(vm.rows, dateBy.id) : null);

	function shiftMonth(delta: number) {
		anchor = new Date(year, month0 + delta, 1);
	}
</script>

{#if !dateBy}
	<div class="prompt" data-testid="calendar-dateby-prompt">
		{#if vm.dateProperties.length > 0}
			<label class="prompt-label">
				Date by
				<select
					class="control"
					data-testid="calendar-dateby-select"
					onchange={(e) => vm.setDateBy(e.currentTarget.value || null)}
				>
					<option value="">Choose a date property…</option>
					{#each vm.dateProperties as property (property.id)}
						<option value={property.id}>{property.name}</option>
					{/each}
				</select>
			</label>
		{:else}
			<p class="hint">Add a date property to place rows on a calendar.</p>
		{/if}
	</div>
{:else}
	<div class="calendar" data-testid="collection-calendar">
		<header class="cal-bar">
			<div class="nav">
				<button
					class="nav-btn"
					data-testid="calendar-prev"
					title="Previous month"
					onclick={() => shiftMonth(-1)}>‹</button
				>
				<button class="nav-btn" data-testid="calendar-today" onclick={() => (anchor = new Date())}
					>Today</button
				>
				<button
					class="nav-btn"
					data-testid="calendar-next"
					title="Next month"
					onclick={() => shiftMonth(1)}>›</button
				>
			</div>
			<h3 class="cal-title" data-testid="calendar-title">{MONTHS[month0]} {year}</h3>
			<label class="prompt-label">
				Date by
				<select
					class="control"
					data-testid="calendar-dateby-select"
					value={dateBy.id}
					onchange={(e) => vm.setDateBy(e.currentTarget.value || null)}
				>
					{#each vm.dateProperties as property (property.id)}
						<option value={property.id}>{property.name}</option>
					{/each}
				</select>
			</label>
		</header>

		<div class="weekdays">
			{#each WEEKDAYS as wd (wd)}
				<div class="weekday">{wd}</div>
			{/each}
		</div>

		<div class="grid" data-testid="calendar-grid">
			{#each weeks as week, wi (wi)}
				{#each week as day (day.getTime())}
					<CollectionCalendarDay
						date={day}
						inMonth={day.getMonth() === month0}
						isToday={dayKey(day) === todayKey}
						rows={grouping?.byDay.get(dayKey(day)) ?? []}
						{onOpenRow}
					/>
				{/each}
			{/each}
		</div>

		{#if grouping && grouping.unscheduled.length > 0}
			<section class="unscheduled" data-testid="calendar-unscheduled">
				<header class="unscheduled-head">
					<span class="unscheduled-count" data-testid="calendar-unscheduled-count"
						>{grouping.unscheduled.length}</span
					>
					unscheduled
				</header>
				<div class="unscheduled-chips">
					{#each grouping.unscheduled as row (row.id)}
						<button
							class="chip"
							data-testid="calendar-unscheduled-chip"
							title={row.title}
							onclick={() => onOpenRow(row.id)}
						>
							{row.title || 'Untitled'}
						</button>
					{/each}
				</div>
			</section>
		{/if}
	</div>
{/if}

<style>
	.prompt {
		padding: 20px 0;
	}
	.prompt-label {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		font-size: 13px;
		color: var(--tx2);
	}
	.hint {
		margin: 0;
		color: var(--tx3);
		font-size: 13px;
	}
	.control {
		padding: 4px 6px;
		border: 1px solid var(--line);
		border-radius: var(--r-control);
		background: var(--bg0);
		color: var(--tx);
		font-size: 13px;
	}
	.calendar {
		display: flex;
		flex-direction: column;
		gap: 12px;
	}
	.cal-bar {
		display: flex;
		align-items: center;
		gap: 12px;
		flex-wrap: wrap;
	}
	.nav {
		display: flex;
		gap: 4px;
	}
	.nav-btn {
		padding: 4px 10px;
		border: 1px solid var(--line);
		border-radius: var(--r-control);
		background: var(--bg0);
		color: var(--tx);
		font-size: 14px;
	}
	.nav-btn:hover {
		background: var(--accbg);
		color: var(--acc-strong);
	}
	.cal-title {
		margin: 0;
		font-size: 16px;
		font-weight: 600;
		color: var(--tx);
	}
	.weekdays,
	.grid {
		display: grid;
		grid-template-columns: repeat(7, 1fr);
	}
	.weekdays {
		gap: 0;
	}
	.weekday {
		padding: 4px 6px;
		font-size: 12px;
		font-weight: 600;
		color: var(--tx2);
		text-align: right;
	}
	.grid {
		border-top: 1px solid var(--line);
		border-left: 1px solid var(--line);
	}
	.grid :global(.cell) {
		border-top: none;
		border-left: none;
	}
	.unscheduled {
		display: flex;
		flex-direction: column;
		gap: 6px;
		border-top: 1px solid var(--line);
		padding-top: 10px;
	}
	.unscheduled-head {
		display: flex;
		align-items: center;
		gap: 6px;
		font-size: 13px;
		color: var(--tx2);
	}
	.unscheduled-count {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-width: 18px;
		height: 18px;
		padding: 0 5px;
		border-radius: 9px;
		background: var(--accbg);
		color: var(--acc-strong);
		font-size: 11px;
		font-weight: 600;
	}
	.unscheduled-chips {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
	}
	.chip {
		text-align: left;
		font-size: 12px;
		padding: 3px 8px;
		border-radius: 4px;
		background: var(--accbg);
		color: var(--acc-strong);
	}
	.chip:hover {
		filter: brightness(0.95);
	}
</style>
