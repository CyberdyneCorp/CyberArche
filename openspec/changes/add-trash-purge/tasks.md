# Tasks

## 1. Domain + application

- [x] 1.1 `DocumentRepository.purge(tenant_id, document_id) -> list[DocumentId]` port (removes subtree, returns purged ids)
- [x] 1.2 `DocumentUseCases.purge`: require trashed (ValidationFailed otherwise) + require editor, then purge
- [x] 1.3 Backend tests, one per scenario: purge removes permanently, cascades to subtree + owned data, live doc rejected, non-editor rejected

## 2. Adapters

- [x] 2.1 Postgres `purge`: collect subtree via recursive CTE, DELETE root (FK cascade removes owned rows + children)
- [x] 2.2 In-memory `purge`: recurse the subtree, remove each from the store
- [x] 2.3 Port-contract test for `purge` (memory + real Postgres): subtree ids returned, owned rows (snapshots/comments/grants/favourites) gone
- [~] 2.4 Agent-run survival on purge: NOT added as a dedicated test. It is a pre-existing schema property (migration 0001 `agent_runs.document_id ON DELETE SET NULL`) that this change only triggers, not introduces; observing it through the ports diverges between adapters (list_for_document can't see a NULL-ref run). Recorded as a design note instead of an over-scoped test.

## 3. HTTP

- [x] 3.1 `DELETE /api/v1/documents/{id}/trash` -> purge; keep `DELETE /{id}` as trash
- [x] 3.2 Regression: purge over HTTP removes the document and its children
