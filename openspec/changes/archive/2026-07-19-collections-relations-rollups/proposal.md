# Collections — relations & rollups

## Why

Collections are isolated tables. Relating a row to rows in another collection,
and rolling up a value across those related rows (count / sum / latest / …), is
the single biggest database capability collections lack — it turns separate
tables into a connected model (Projects ↔ Tasks, with a "task count" rollup).

## What Changes

- Add a `relation` property type: its value is a set of links to rows (documents)
  of a target collection. Setting it validates that each linked row belongs to
  the target collection and the caller's tenant.
- Add a `rollup` property type: a read-only column that aggregates a chosen
  property of the rows reached through a relation, via a function (count, sum,
  average, min, max, earliest, latest, list). Computed server-side in
  `query_view` (reusing the formula-era computed-property machinery).
- The row-query result includes the id + title of every linked row so relation
  cells can render titles; a lightweight endpoint lists a target collection's
  rows for the relation picker.

## Impact

- Affected specs: `collections`.
- Affected code: domain (`RELATION`/`ROLLUP` types, relation/rollup config on
  `PropertyDef`, aggregation), use case (validate/coerce relations, compute
  rollups, resolve linked titles), postgres (de)serialization, router (rows
  response + list-rows endpoint); frontend relation picker cell, rollup cell,
  and the add-property UI. No new table (relation values live in row properties).
