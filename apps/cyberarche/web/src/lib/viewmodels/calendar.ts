/** Calendar pure helpers (Model/logic layer, DOM-free and deterministic).
 *
 * The week starts on MONDAY. None of these functions call `new Date()` with no
 * arguments — the anchor month is always passed in explicitly — so they never
 * read the ambient clock and are fully unit-testable. Only the Calendar
 * component reads "today". */

import type { CollectionRow } from '$lib/api/collections';

function pad2(n: number): string {
	return n < 10 ? `0${n}` : `${n}`;
}

/** Pure: a row's date property parsed to a 'YYYY-MM-DD' local-date key. */
export function dayKey(date: Date): string {
	return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`;
}

/** Pure: weeks (rows) of 7 days covering `month0` (0-based) of `year`, with
 * leading days from the previous month and trailing days from the next so every
 * week is full. Week starts on Monday; the last day is a Sunday. */
export function monthGrid(year: number, month0: number): Date[][] {
	const first = new Date(year, month0, 1);
	const lead = (first.getDay() + 6) % 7; // Monday=0 … Sunday=6
	const last = new Date(year, month0 + 1, 0); // last day of the month
	const trail = 6 - ((last.getDay() + 6) % 7);
	const weekCount = (lead + last.getDate() + trail) / 7;

	const weeks: Date[][] = [];
	for (let w = 0; w < weekCount; w++) {
		const week: Date[] = [];
		for (let d = 0; d < 7; d++) {
			// Date normalises day over/underflow, rolling into adjacent months.
			week.push(new Date(year, month0, 1 - lead + w * 7 + d));
		}
		weeks.push(week);
	}
	return weeks;
}

/** Pure: the 'YYYY-MM-DD' key for a row's `dateByPropertyId` value, or null when
 * the value is missing or unparseable. ISO date/timestamp strings use their
 * written calendar date (no timezone shift); other strings fall back to Date. */
export function rowDateKey(row: CollectionRow, dateByPropertyId: string): string | null {
	const raw = row.properties[dateByPropertyId];
	if (typeof raw !== 'string' || raw.trim() === '') return null;
	const iso = /^(\d{4}-\d{2}-\d{2})/.exec(raw.trim());
	if (iso) return iso[1];
	const parsed = new Date(raw);
	return Number.isNaN(parsed.getTime()) ? null : dayKey(parsed);
}

/** Rows bucketed by day key, plus rows with no valid date. */
export interface DayGrouping {
	byDay: Map<string, CollectionRow[]>;
	unscheduled: CollectionRow[];
}

/** Pure: bucket already-filtered/sorted rows by their date-property day key.
 * Rows with a null key go to `unscheduled`. Within-bucket order mirrors the
 * incoming row order. */
export function groupRowsByDay(rows: CollectionRow[], dateByPropertyId: string): DayGrouping {
	const byDay = new Map<string, CollectionRow[]>();
	const unscheduled: CollectionRow[] = [];
	for (const row of rows) {
		const key = rowDateKey(row, dateByPropertyId);
		if (key === null) {
			unscheduled.push(row);
			continue;
		}
		const bucket = byDay.get(key);
		if (bucket) bucket.push(row);
		else byDay.set(key, [row]);
	}
	return { byDay, unscheduled };
}
