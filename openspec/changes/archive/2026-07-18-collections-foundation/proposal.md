# Collections (databases) — foundation + Table view

## Why

CyberArche has documents, blocks, and a whiteboard, but no way to manage a *set*
of pages with structured properties — the single biggest structural feature a
Notion-style tool has that this lacks. This introduces collections (databases)
where each row is a full document (blocks, comments, permissions) carrying typed
property values, presented first as an editable Table view. Later changes add
filter/sort and the Board, Gallery, and Calendar views.

## What Changes

- Domain: a `Collection` (workspace-scoped) with a property schema
  (`PropertyDef`: text, number, select, multi_select, date, checkbox, url) and
  named `View`s (kind table|board|gallery|calendar, with filters, sorts,
  group-by, date-by defined now for forward compatibility). Each **row is a
  Document**: `Document` gains a `collection_id` and typed `properties`.
- A pure `apply_view(rows, view)` applying filters then sorts (used by every
  view; the Table view uses it now).
- Use cases: collection CRUD, property-schema edits, view CRUD, row operations
  (add row = create a member document; set a row's property value; remove row),
  and querying a view's rows — all access-scoped to the workspace.
- Repositories (in-memory + postgres) + migration; a REST router.
- Frontend: create/list collections from the sidebar and a collection page
  rendering an editable Table view (typed cell editors, add row, add property,
  open a row as its document).

## Impact

- Affected specs: `collections` (new); `document-model` (documents gain
  collection membership + properties).
- Affected code: domain (collections, Document fields), ports + both repo
  backends, migration, use cases, router, wiring; frontend api client, VM,
  sidebar, and a collection route with the Table view. Data-model change →
  OpenSpec-tracked.
