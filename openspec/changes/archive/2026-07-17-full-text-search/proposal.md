# Full-text + semantic search

## Why

Search is title-only today (`document-search`). Users can't find a document by
its *content*, and the RAG "answer" capability (already exposed at
`/workspaces/{id}/knowledge/query`) isn't surfaced in the search UI. Both the
block-content read path (used by backlinks/graph) and RAG already exist — this
wires them into a real search experience.

## What Changes

- Add `SearchUseCases.search(caller, workspace_id, query, limit)` returning
  hits that match a document's **title or block content**, each with a short
  snippet and which field matched. Access-scoped (only docs the caller may
  view), reusing the same CRDT block-read path as the graph.
- New endpoint `GET /workspaces/{id}/search/content?q=&limit=`.
- Command palette (⌘K) shows content snippets alongside title matches, and adds
  an "Ask AI" row that calls the existing `/knowledge/query` for a RAG answer.

## Impact

- Affected specs: `document-search`.
- Affected code: new `application/use_cases/search.py`; `use_cases/__init__.py`
  + wiring container; a search router; `CommandPalette.svelte` + a small
  `api/search.ts`. No migration (search reads live block text + existing RAG).
