import { describe, expect, it } from 'vitest';

import type { CollectionRow } from '$lib/api/collections';
import { dayKey, groupRowsByDay, monthGrid, rowDateKey } from './calendar';

const rowWith = (id: string, value: unknown): CollectionRow =>
	({ id, properties: value === undefined ? {} : { d: value } }) as unknown as CollectionRow;

describe('dayKey', () => {
	it('formats a zero-padded local YYYY-MM-DD key', () => {
		expect(dayKey(new Date(2026, 6, 5))).toBe('2026-07-05');
		expect(dayKey(new Date(2026, 11, 31))).toBe('2026-12-31');
	});
});

describe('monthGrid (Monday-start)', () => {
	it('includes leading/trailing days for January 2026 (5 weeks)', () => {
		const weeks = monthGrid(2026, 0);
		expect(weeks).toHaveLength(5);
		expect(weeks.every((w) => w.length === 7)).toBe(true);
		expect(dayKey(weeks[0][0])).toBe('2025-12-29'); // prev-month Monday
		expect(dayKey(weeks[0][3])).toBe('2026-01-01'); // Jan 1 is a Thursday
		expect(dayKey(weeks[4][6])).toBe('2026-02-01'); // next-month Sunday
		expect(weeks[0][0].getDay()).toBe(1); // first cell is a Monday
		expect(weeks[4][6].getDay()).toBe(0); // last cell is a Sunday
	});

	it('spans 6 weeks for March 2025 with correct first/last cells', () => {
		const weeks = monthGrid(2025, 2);
		expect(weeks).toHaveLength(6);
		expect(dayKey(weeks[0][0])).toBe('2025-02-24'); // leading Monday
		expect(dayKey(weeks[5][6])).toBe('2025-04-06'); // trailing Sunday
	});

	it('is exactly 4 weeks when February starts on a Monday (2021)', () => {
		const weeks = monthGrid(2021, 1);
		expect(weeks).toHaveLength(4);
		expect(dayKey(weeks[0][0])).toBe('2021-02-01');
		expect(dayKey(weeks[3][6])).toBe('2021-02-28');
	});

	it('covers February 2024 through the leap-day 29th', () => {
		const keys = monthGrid(2024, 1).flat().map(dayKey);
		expect(keys).toContain('2024-02-29');
		expect(keys).not.toContain('2024-02-30');
	});

	it('excludes Feb 29 in the non-leap year 2025', () => {
		const keys = monthGrid(2025, 1).flat().map(dayKey);
		expect(keys).toContain('2025-02-28');
		expect(keys).not.toContain('2025-02-29');
	});
});

describe('rowDateKey', () => {
	it('parses an ISO date string', () => {
		expect(rowDateKey(rowWith('r', '2026-07-15'), 'd')).toBe('2026-07-15');
	});

	it('parses a full ISO timestamp to its written date part (no TZ shift)', () => {
		expect(rowDateKey(rowWith('r', '2026-07-15T10:30:00Z'), 'd')).toBe('2026-07-15');
	});

	it('returns null for missing, empty, garbage, or non-string values', () => {
		expect(rowDateKey(rowWith('r', undefined), 'd')).toBeNull();
		expect(rowDateKey(rowWith('r', ''), 'd')).toBeNull();
		expect(rowDateKey(rowWith('r', 'not-a-date'), 'd')).toBeNull();
		expect(rowDateKey(rowWith('r', 12345), 'd')).toBeNull();
	});
});

describe('groupRowsByDay', () => {
	it('buckets rows by day, preserves within-day order, collects unscheduled', () => {
		const rows = [
			rowWith('a', '2026-07-15'),
			rowWith('b', '2026-07-15T09:00:00Z'),
			rowWith('c', undefined),
			rowWith('d', '2026-07-16'),
			rowWith('e', 'garbage')
		];
		const { byDay, unscheduled } = groupRowsByDay(rows, 'd');
		expect(byDay.get('2026-07-15')?.map((r) => r.id)).toEqual(['a', 'b']);
		expect(byDay.get('2026-07-16')?.map((r) => r.id)).toEqual(['d']);
		expect(unscheduled.map((r) => r.id)).toEqual(['c', 'e']);
	});

	it('returns empty structures for no rows', () => {
		const { byDay, unscheduled } = groupRowsByDay([], 'd');
		expect(byDay.size).toBe(0);
		expect(unscheduled).toEqual([]);
	});
});
