## 1. Agent editing + insertable answers

- [x] 1.1 `CrdtEnginePort.update_block` / `delete_block` + pycrdt adapter (data merge, not replace)
- [x] 1.2 `AgentUseCases`: per-run document-bound tools (insert_blocks / update_block / delete_block), dispatched before the global registry; block ids in the prompt context
- [x] 1.3 `ask()` returns text + insertable blocks; HTTP `AskResponse` carries them
- [x] 1.4 Tests: agent adds text to an existing block, inserts, deletes; viewer denied; tools cannot touch another document; answers carry blocks

## 2. Teamspaces + favourites (backend)

- [x] 2.1 Domain: `Teamspace`, `TeamspaceMembership`, `Favorite`; `Document.teamspace_id`
- [x] 2.2 Ports + in-memory fakes + Postgres adapters + `0006_teamspaces_favorites` migration
- [x] 2.3 `AccessControl`: effective role = strongest(workspace, teamspace), document grant overrides
- [x] 2.4 `TeamspaceUseCases` (create/list/members/documents) and `FavoriteUseCases` (add/remove/list)
- [x] 2.5 HTTP routers: `/workspaces/{id}/teamspaces`, `/teamspaces/{id}/members`, `/favorites`
- [x] 2.6 Tests: creation, membership grants access, non-member denied, cross-workspace rejected, favourites are private; repository contract suite

## 3. Web

- [x] 3.1 Block delete control in the editor gutter (undoable)
- [x] 3.2 Agent message actions: Insert as block / Replace selection / Copy on every answer
- [x] 3.3 Sidebar: workspace switcher (current, new workspace, settings)
- [x] 3.4 Sidebar sections: Favorites, Teamspaces (with documents), Shared with me
- [x] 3.5 Create teamspace + add document to teamspace from the sidebar
- [x] 3.6 Vitest for the new ViewModels; e2e: delete a block, agent edits the open document, create a teamspace, switch workspace
