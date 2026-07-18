# Tasks
- [ ] 1.1 `DocumentUseCases.path` — workspace → teamspace? → folders(root→leaf) → ancestor docs(root→parent) → self; view-access scoped; cycle-guarded
- [ ] 1.2 Add the workspace repo dep to DocumentUseCases + wiring
- [ ] 1.3 `GET /api/v1/documents/{id}/path` endpoint
- [ ] 1.4 Frontend: getDocumentPath client + render crumbs in the doc top bar (workspace + ancestor docs link; self is text; last crumb tracks the title)
- [ ] 1.5 Tests: path ordering + names (nested folders/docs, root doc), access enforced, cycle guard; frontend api + breadcrumb render/links
- [ ] 1.6 `openspec validate document-breadcrumb --strict`; gates green
