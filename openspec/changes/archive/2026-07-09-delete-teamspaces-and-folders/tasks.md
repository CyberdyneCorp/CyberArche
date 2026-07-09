# Tasks

## Backend — teamspace delete
- [x] Add `TeamspaceRepository.delete(tenant_id, teamspace_id)` to the port
- [x] Implement it in the in-memory fake and the Postgres repo
- [x] Inject `FolderRepository` into `TeamspaceUseCases`; add `delete(caller, teamspace_id)` requiring OWNER that trashes+detaches all teamspace documents, deletes its folders, then deletes the teamspace
- [x] Add `DELETE /api/v1/teamspaces/{teamspace_id}` endpoint + wiring

## Backend — folder delete cascade
- [x] Change `FolderUseCases.delete` to trash the subtree's documents (instead of detaching)

## Backend tests
- [x] Teamspace delete moves docs (incl. foldered) to trash and removes folders; non-owner refused; restore works
- [x] Folder delete moves its documents to trash; sub-folder docs too
- [x] Update the existing `test_folders` detach test to the new trash behavior
- [x] HTTP contract test for `DELETE /teamspaces/{id}`

## Frontend — toast + dialog infrastructure
- [x] `toasts` viewmodel + `Toasts.svelte` container mounted in root `+layout.svelte`
- [x] `dialogs` viewmodel (promise-based `confirm`/`prompt`) + `ConfirmDialog.svelte` mounted in root layout
- [x] Replace native `confirm()` (purge) and `prompt()` (folder name) in `Sidebar.svelte`

## Frontend — delete affordance
- [x] `ContextMenu.svelte` opened by a kebab (⋯) button and by right-click on teamspace/folder rows
- [x] Delete action → confirm dialog → API call → toast + refresh
- [x] `api/teamspaces.ts`: `deleteTeamspace(id)`

## Verify
- [x] Backend suite, vitest, full e2e (Playwright), typecheck, import-linter
- [x] e2e: delete a folder (docs to trash) and a teamspace via the menu + confirm dialog
