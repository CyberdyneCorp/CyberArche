# Tasks

## 1. Backend graph query
- [x] 1.1 `LinksUseCases.graph(caller, *, teamspace_id|folder_id)` → nodes (in-scope docs) + edges (resolved in-scope `[[title]]` links)
- [x] 1.2 Access-filter per document (viewer role); dedupe edges; ignore self-links
- [x] 1.3 `GET /teamspaces/{id}/graph` + `GET /folders/{id}/graph` returning `{nodes, edges}`
- [x] 1.4 Tests: edges only between in-scope docs; case-insensitive title match; unreadable docs excluded

## 2. Frontend graph modal
- [x] 2.1 `api/links.ts`: `teamspaceGraph(id)`, `folderGraph(id)`
- [x] 2.2 `viewmodels/graph-view.svelte.ts` singleton: `open({scope,id,name})` / `close()`
- [x] 2.3 `GraphModal.svelte`: force-directed SVG layout, zoom (wheel) + pan (drag), double-click node → close + goto document
- [x] 2.4 Sidebar: add "Open graph" to the teamspace and folder context menus
- [x] 2.5 Mount `<GraphModal>` in the workspace layout

## 3. Validate
- [x] 3.1 `openspec validate wikilink-graph-view --strict`
- [x] 3.2 Backend tests + import-linter; web typecheck + build
