# Tasks

## Backend
- [x] Add `move_to_teamspace(caller, document_id, teamspace_id)` to `DocumentUseCases` (sets teamspace, clears folder, requires EDITOR + teamspace membership)
- [x] Replace `POST /documents/{id}/folder` with `POST /documents/{id}/location` accepting `folder_id` | `teamspace_id` | neither
- [x] Regression tests: move a document to a teamspace; move a foldered doc out to private (`tests/test_folders.py`)
- [x] Update HTTP contract test to the `/location` endpoint (`tests/test_http_api.py`)

## Frontend
- [x] `api/folders.ts`: `placeInFolder`, `moveToTeamspace`, `moveToPrivate` all POST `/location`
- [x] Sidebar: make document rows draggable; teamspace/folder rows and Private section are drop targets
- [x] Sidebar: star / add-child / trash actions on teamspace and folder document rows
- [x] Enlarge the disclosure caret in `Sidebar.svelte` and `TreeItem.svelte`
- [x] e2e: drag a private doc into a teamspace, then star and trash it there (`e2e/07-teamspaces-and-agent-editing.spec.ts`)

## Verify
- [x] Backend suite (218 passed), vitest (62 passed), full e2e (32 passed), typecheck 0 errors, import-linter clean
