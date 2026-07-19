# Collections — formula (computed) properties

## Why

Collection properties are all manually entered. A formula property — a read-only
column derived from an expression over the row's other properties (e.g. "Days
until Due", "Overdue?" from a date, "Total" from price × qty) — is the highest
daily-use database capability still missing, and it establishes the
server-computed-property machinery that rollups will reuse.

## What Changes

- Add a `formula` property type carrying an expression. Values are computed
  server-side (never stored, never edited) from the row's other non-formula
  properties and its title, and are included in `query_view` results so they can
  be displayed, filtered, and sorted like any column.
- A safe, bounded expression evaluator (no `eval`): arithmetic, comparisons,
  boolean logic, `if(...)`, and a small function set, with `prop("Name")`
  resolving another property's value and `now()` the current time. Invalid
  expressions are rejected when the property is created/edited.

## Impact

- Affected specs: `collections`.
- Affected code: domain (`PropertyType.FORMULA`, `PropertyDef.formula`, a pure
  evaluator), `CollectionUseCases` (validate on add/update, reject writes,
  compute in `query_view`), the postgres schema (de)serialization of the new
  field; frontend property editor + read-only formula cell. No new table.
