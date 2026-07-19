# Collections — bulk row actions

## Why

Collection tables can only act on one row at a time. Selecting many rows to set a
property on all of them (e.g. mark a batch "Done") or delete them together is
basic table ergonomics the database currently lacks.

## What Changes

- Multi-select rows in the table (per-row + select-all), with a bulk action bar.
- Bulk **delete** selected rows and bulk **set a property value** across selected
  rows, each access-checked per row; formula/rollup properties are not settable.
- Backend batch use-case methods + endpoints returning how many rows changed.

## Impact

- Affected specs: `collections`.
- Affected code: `CollectionUseCases` (delete_rows, set_rows_value), router
  (bulk endpoints); frontend selection state + bulk action bar. No migration.
