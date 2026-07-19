# Reconcile the inline database block with collections

## Why

There are two databases: the full-page `collections` capability (rich: formula,
relations, rollups, reminders, bulk, four views) and an older inline `database`
block (CRDT-stored, far less capable). They overlap and diverge. Reconcile them
by making the inline database a collection embedded in the document — one backend,
shared view/cell components, and every collection feature available inline.

## What Changes

- Add a `collection_view` block that references a collection and a view. Inserting
  a "Database" from the slash menu creates a collection in the workspace and
  embeds it; the block renders the collection's views (table/board/gallery/
  calendar) inline using the same components as the full-page collection, with
  full editing.
- The legacy `database` block is retained so existing documents keep rendering,
  but it is no longer offered for new inserts (forward path is collection-backed).

## Impact

- Affected specs: `collections`.
- Affected code: `collection_view` in the block types (domain BLOCK_TYPES); a new
  block component reusing the collection view components; block registry + slash
  menu (new entry, legacy hidden). Reuses the existing collection endpoints — no
  new backend endpoint or migration.
