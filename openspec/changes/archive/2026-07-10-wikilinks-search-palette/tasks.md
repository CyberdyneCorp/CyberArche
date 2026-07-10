# Tasks

## Backend
- [x] `GET /workspaces/{id}/search?q=` → title search scoped to workspace access
- [x] `documents.backlinks(caller, document_id)` — scan workspace docs' block text for `[[title]]`; `GET /documents/{id}/backlinks`
- [x] Tests: search returns/【scopes】 matches; backlinks finds a referencing doc

## Frontend — wikilinks
- [x] inline renderer: tokenize `[[Name]]` → resolved link (by title) or unresolved link
- [x] `[[` autocomplete in the editor (title lookup) + insert `[[Title]]`
- [x] navigate on click; unresolved styling
- [x] Tests: inline `[[…]]` rendering (resolved/unresolved)

## Frontend — search + palette + backlinks
- [x] `api` search client; Cmd/Ctrl+K palette (mounted in workspace layout): search + open + create
- [x] Backlinks panel on the document
- [x] e2e: create link A→B, backlink shows on B; Cmd+K jumps to a doc

## Verify
- [x] Backend suite + import-linter; typecheck, vitest, full e2e
