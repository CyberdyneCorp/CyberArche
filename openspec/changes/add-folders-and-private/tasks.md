# Tasks

## 1. Domain + data model
- [x] 1.1 `Folder` domain aggregate; `FolderId`
- [x] 1.2 Migration: `folders` table (teamspace_id, parent_folder_id) + `documents.folder_id` (ON DELETE SET NULL)
- [x] 1.3 `Document.folder_id` field

## 2. Application
- [x] 2.1 AccessControl: private rule (teamspace-less doc -> grant | owner-if-creator | none)
- [x] 2.2 FolderRepository port + in-memory + postgres adapters
- [x] 2.3 FolderUseCases: create (teamspace/private), list_for_workspace (scoped), children, rename, delete
- [x] 2.4 DocumentUseCases: place_in_folder (adopt folder scope) / move to private; list_private (caller's teamspace-less roots)
- [x] 2.5 Tests: private access rule, folder create/list/nest/delete-detaches, place-in-folder scope, list_private scoping

## 3. HTTP + contract
- [x] 3.1 Routes: folders CRUD; place document in folder / teamspace / private; list private; list folder contents
- [x] 3.2 Port-contract test for FolderRepository (memory + postgres), incl. folder_id cascade on doc

## 4. Sidebar
- [ ] 4.1 Rename Documents -> Private (owner-only listing); render folders under teamspaces + private
- [ ] 4.2 Create folder; add document to a folder; expand/collapse folders
- [ ] 4.3 vitest for the folders/private ViewModel; e2e: create folder in a teamspace, add a doc, private doc not shown to others
