# Wikilink graph view (Obsidian-style)

## Why

Documents are already connected through `[[wikilinks]]`, but there's no way to
*see* those relationships. Users want an Obsidian-style graph to visualize how
the documents in a teamspace or folder link to each other, and to jump straight
into a document from the graph.

## What Changes

- Add a link-graph query: for a teamspace or folder, return its documents as
  nodes and the resolved `[[title]]` links between those documents as edges.
  Reuses the existing wikilink scan (realtime state → blocks → `[[…]]` regex)
  and title resolution.
- Endpoints: `GET /teamspaces/{id}/graph` and `GET /folders/{id}/graph`,
  returning `{nodes: [{id, title}], edges: [{source, target}]}`, access-filtered
  per document (a caller only sees documents they may view).
- Right-clicking a teamspace or folder in the sidebar gains an **Open graph**
  item that opens a modal graph view.
- The modal renders a force-directed graph the user can **zoom** (in/out) and
  **pan**; **double-clicking a node closes the modal and opens that document**.
  Rendered with a small self-contained force simulation (no new dependency).

## Impact

- Affected specs: `document-links` (link graph query + graph view).
- Affected code: `LinksUseCases.graph`; teamspaces + folders HTTP routers;
  web `api/links` client, `graph-view` store, `GraphModal.svelte`, Sidebar menu
  items, workspace layout mount.
- No change to storage, auth, or the wikilink format.
