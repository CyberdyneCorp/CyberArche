# Database block (typed rows + views)

## Why

The biggest gap versus Notion is structured data: a table of rows with typed
properties, viewable as a grid or a kanban board. This turns CyberArche from a
document tool into a light workspace database.

## What Changes

- Add a `database` block: a schema of typed properties plus rows of records.
- Property types (MVP): text, number, select (with options), checkbox, date.
- Views (MVP): a **Table** view (editable grid; add/remove rows and columns;
  rename a column; change its type; sort by a column) and a **Board** view
  (kanban grouped by a select property; move a card between groups; add a card).
- The database lives entirely in the block's document CRDT — rows in a per-block
  shared map (so concurrent row edits merge), mirrored into the block's `data`
  for snapshots/agent/export — so **no new backend storage** is required.
- Whitelist `database` in the backend block types.

Deferred (documented, not built now): calendar/gallery/list views, filters,
relations, rollups, rows-as-pages, formula/person property types.

## Impact

- Affected specs: `document-model` (the database block + its properties/views).
- Affected code: `domain/blocks.py` whitelist; web `viewmodels/database.svelte`
  (schema + rows over a per-block Y.Map), `DatabaseBlock.svelte` (table + board),
  block registry.
- No migration, no new endpoint — the block is CRDT-native like the whiteboard.
