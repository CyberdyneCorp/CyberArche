# Tasks

## 1. Backend: document content read
- [x] 1.1 `RealtimeUseCases.read_blocks(caller, document_id)` (viewer access)
- [x] 1.2 `GET /documents/{id}/blocks` → `{blocks}`
- [x] 1.3 Test: returns the document's blocks; unauthorized caller rejected

## 2. Frontend: ZIP export
- [x] 2.1 Add `jszip`; `api/documents.documentBlocks(id)`
- [x] 2.2 Scope ZIP builder: fetch scope docs → each doc's blocks → toMarkdown (images inlined) → zip → download
- [x] 2.3 Sidebar: "Export (ZIP)" on teamspace and folder context menus (toast feedback)

## 3. Frontend: teamspace members
- [x] 3.1 `api/teamspaces.removeTeamspaceMember`
- [x] 3.2 `TeamspaceMembersDialog`: invite by user id + role, list members, remove
- [x] 3.3 Sidebar: "Manage members" on the teamspace context menu

## 4. Validate
- [x] 4.1 `openspec validate teamspace-export-and-members --strict`; backend + web green
