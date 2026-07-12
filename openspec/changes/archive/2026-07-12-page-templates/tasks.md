# Tasks

## 1. Store + use case
- [x] 1.1 Migration `0011_templates.sql` (id, tenant, workspace_id, name, created_by, created_at, content jsonb) + RLS
- [x] 1.2 `Template` domain + `TemplateRepository` (add, list_for_workspace, get, delete) + in-memory + Postgres
- [x] 1.3 `TemplateUseCases`: save_from_document, instantiate (fresh block ids), list, delete
- [x] 1.4 Wire into container
- [x] 1.5 Tests: save captures blocks; instantiate creates a doc with those blocks (new ids); delete

## 2. HTTP
- [x] 2.1 POST /workspaces/{id}/templates, GET /workspaces/{id}/templates, POST /workspaces/{id}/templates/{tid}/instantiate, DELETE /templates/{tid}

## 3. Frontend
- [x] 3.1 `api/templates`
- [x] 3.2 Document page: "Save as template"
- [x] 3.3 Sidebar "New document": a "From template" picker that instantiates + opens

## 4. Validate
- [x] 4.1 `openspec validate page-templates --strict`; backend + import-linter; web typecheck + build
