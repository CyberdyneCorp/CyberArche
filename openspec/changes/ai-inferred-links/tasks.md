# Tasks

## 1. Cache store
- [x] 1.1 Migration `0009_inferred_links.sql`: `document_inferred_links` (source_document_id PK, tenant_id, content_hash, computed_at, payload jsonb) + RLS
- [x] 1.2 `InferredLinkRepository` port (get_many, put) + record value type
- [x] 1.3 In-memory + Postgres adapters
- [x] 1.4 Wire into the container + LinksUseCases

## 2. Inference + typed edges
- [x] 2.1 Extend `GraphEdge` with `type`, `confidence`, `evidence`, `inferred`
- [x] 2.2 `LinksUseCases.inferred_graph`: content-hash per doc; classify only new/changed docs via the LLM; cache the rest
- [x] 2.3 LLM classification → typed relationships (depends_on/explains/cites/similar/contradicts/mentions) + confidence + evidence; drop low confidence; tolerate bad JSON
- [x] 2.4 `GET /teamspaces/{id}/graph/inferred` + `/folders/{id}/graph/inferred`

## 3. Caching behaviour
- [x] 3.1 Test: first call classifies each doc once; second call (unchanged) makes ZERO LLM calls
- [x] 3.2 Test: changing a document's content re-infers only that document

## 4. Frontend
- [x] 4.1 `api/links`: `teamspaceInferredGraph`, `folderInferredGraph`; typed edge fields
- [x] 4.2 GraphModal: "AI links" toggle → fetch inferred graph (loading state, client-cached per scope)
- [x] 4.3 Render inferred edges dashed, coloured by type, thickness by confidence; edge-type legend
- [x] 4.4 Inspector: list the selected document's typed relationships (type · confidence · evidence)

## 5. Validate
- [x] 5.1 `openspec validate ai-inferred-links --strict`; backend + import-linter; web typecheck + build
