# AI-inferred typed relationships in the graph

## Why

The graph explorer only shows explicit `[[wikilinks]]`. Users want to see *why*
documents relate — prerequisites, explanations, citations, similarity,
contradictions — not just that a link exists. An LLM can infer these typed
relationships from the documents' content.

Inference is expensive, so it MUST be cached: re-opening the graph window (or
toggling AI links) SHALL NOT re-ask the LLM for documents that haven't changed.

## What Changes

- Add an inferred-links cache keyed **per source document by a content hash**.
  When the graph is requested with inference on, each in-scope document is
  classified only if it is new or its content changed since last inference;
  unchanged documents are served from the cache (zero LLM calls on re-open).
- Add an LLM classification step: for a document, infer its typed relationships
  to the other in-scope documents — `depends_on`, `explains`, `cites`, `similar`,
  `contradicts`, `mentions` — each with a confidence (0–100) and a short
  evidence string. Low-confidence relationships are dropped.
- Extend the graph edges with `type`, `confidence`, `evidence`, and an
  `inferred` flag. Explicit `[[links]]` remain `links_to`, `inferred: false`.
- New endpoints `GET /teamspaces/{id}/graph/inferred` and
  `GET /folders/{id}/graph/inferred` returning nodes + typed edges, using the
  cache.
- Frontend: an **AI links** toggle in the graph. When on, inferred edges render
  dashed and coloured by type with thickness by confidence; the node inspector
  lists a document's typed relationships (type · confidence · evidence). A legend
  explains the edge types.

## Impact

- Affected specs: `document-links` (typed inferred relationships + caching).
- Data model: new `document_inferred_links` table (migration
  `0009_inferred_links.sql`) — the cache.
- Affected code: `InferredLinkRepository` port + in-memory + Postgres adapters;
  `LinksUseCases.inferred_graph` (LLM classify + cache) and an extended
  `GraphEdge`; teamspaces + folders routers; wiring; web `api/links`, GraphModal.
- Cost/latency: first inference of a folder calls the LLM once per document; all
  subsequent opens are cache hits until a document changes. Access is unchanged
  (the caller only sees documents they may view; the classification runs
  server-side with the model already configured).
