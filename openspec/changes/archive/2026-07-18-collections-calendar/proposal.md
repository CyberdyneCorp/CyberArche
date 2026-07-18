# Collections — Calendar view

## Why

The Calendar view is the last of the four planned collection view kinds. The
view model already carries a `date_by` field (which now persists), so this is the
frontend month-grid renderer that places rows on their date property.

## What Changes

- Calendar view: a month grid that places each row on the day matching a chosen
  date property (`date_by`), with month navigation (previous/next/today). Rows
  whose date is missing or unparseable are surfaced as an "unscheduled" count.
- Members choose the date property; clicking a row opens it as its page.
- The view honors the active filters/sorts.

## Impact

- Affected specs: `collections`.
- Affected code: frontend only — a Calendar component, the date-property picker,
  and small pure date helpers (month grid, group-rows-by-day). Backend already
  supports it.
