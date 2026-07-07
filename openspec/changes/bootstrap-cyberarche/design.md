## Context

CyberArche is a greenfield, AI-centric collaborative document platform. It reuses
the architectural idioms proven in `~/work/tessera` (FastAPI + Hexagonal backend,
Svelte 5 MVVM frontend, Yjs/CRDT sync) but adds three things Tessera does not
have: a FastMCP tool surface, a RAG knowledge layer (CyberdyneRAG), and a
first-class per-document AI agent. Identity is delegated to CyberdyneAuth
(OIDC/OAuth2 + JWT/JWKS). This document records the cross-cutting decisions that
the ten capability specs depend on.

Constraints:
- Backend: Python 3.12+, FastAPI, FastMCP, Hexagonal, import-linter boundaries.
- Frontend: Svelte 5 runes, strict MVVM (View `.svelte` / ViewModel `.svelte.ts`
  / Model `.ts`).
- External, owned services: CyberdyneAuth and CyberdyneRAG (schemas already
  published as OpenAPI).
- Global rules: OpenSpec for security/data-model/full-stack work; regression test
  per bug fix; backend cognitive complexity ≤15.

## Goals / Non-Goals

**Goals:**
- A working vertical foundation across all ten capabilities — not a stub.
- CRDT multiplayer with the AI agent as a peer editor.
- One composition root shared by three deployables (`api`, `mcp`, `workers`).
- Provider-agnostic LLM; permissions enforced identically on HTTP, realtime, MCP.

**Non-Goals:**
- Building our own auth or vector store — we integrate CyberdyneAuth/CyberdyneRAG.
- Public marketplace of MCP connectors (only user-registered external servers).
- Mobile app; advanced database views (Notion-style relations/rollups) — later.
- Fine-grained per-block ACL beyond block comments (document-level is the unit).

## Decisions

### D-1 — CRDT via Yjs with a FastAPI relay and pycrdt on the server
Documents are a single Yjs doc (block tree + whiteboard scenes as subdocuments/
shared types). Clients sync over WebSocket to a FastAPI relay behind a
`CrdtEnginePort`; the server uses `pycrdt` to hold authoritative state, persist
the update log, and compact snapshots to Postgres. **Rationale:** matches the
chosen product decision (Google-Docs-style multiplayer, offline merge), lets the
AI agent apply edits as a server-side peer, and mirrors Tessera's proven
`crdt-and-yjs` approach. **Alternative rejected:** server-authoritative OT — worse
offline story and harder agent-as-peer editing.

### D-2 — Blocks and whiteboard live inside the CRDT, snapshots are derived
The canonical content is the Yjs doc. A materialized JSON block tree + state
vector is snapshotted periodically for fast reads, search indexing, and RAG
ingestion. **Rationale:** one source of truth for concurrent edits; reads and
ingestion don't need a live CRDT session. **Trade-off:** snapshots lag the live
doc slightly; acceptable for read/index paths.

### D-3 — Provider-agnostic LLM behind `LLMPort`
The agent depends on `LLMPort` (chat/completions + tool-calling). Adapters wrap
Anthropic/OpenAI/local, selected by config (LiteLLM as the default multiplexer).
**Rationale:** the product decision was provider-agnostic; keeps domain/use cases
free of vendor SDKs. Default target: latest Claude models.

### D-4 — FastMCP shares the composition root with the HTTP API
`services/cyberarche/mcp` builds the same `Container` as `services/cyberarche/api`
and exposes `@mcp.tool` functions that resolve `use_cases` and a `CallerContext`
from a verified token — exactly as HTTP routers do. **Rationale:** tools and HTTP
handlers are two inbound adapters over identical use cases, so authorization and
tenant scoping are enforced once, in the use cases, and cannot diverge.

### D-5 — External MCP servers behind `McpClientPort`, tools namespaced
The agent aggregates tools from CyberArche's own server plus user-registered
external MCP servers via an `McpClientPort`. External tools are namespaced by
connector; credentials are encrypted at rest (reusing the auth service's
custodial-key patterns is out of scope — use app-level envelope encryption).
**Rationale:** extensibility without name collisions; per-session opt-in bounds
blast radius.

### D-6 — Auth is a port; tenant/identity come only from verified claims
`TokenPort`/`AuthProviderPort` verify JWTs against CyberdyneAuth JWKS (introspect
for opaque/service tokens). `require_caller` builds `CallerContext(user_id,
tenant_id, roles)` from claims — never from path/body. IAM decisions delegate to
CyberdyneAuth's `iam/evaluate` where policy evaluation is needed. **Rationale:**
structural, non-spoofable tenant isolation; mirrors Tessera's 401-before-use-case
seam. Postgres RLS provides defense-in-depth.

### D-7 — RAG project per workspace
Workspace creation provisions an isolated CyberdyneRAG `project_slug`. Ingestion
uploads originals to RAG and tracks the returned task (poll + optional callback
webhook). Retrieval uses `RagPort.query(mode)`. **Rationale:** RAG already
guarantees per-project isolation; mapping 1:1 to workspace inherits tenant
isolation for free.

### D-8 — Ingestion & long AI runs go through workers
File ingestion (PDF/CSV/Excel → blocks + RAG) and long agent runs execute in
`services/cyberarche/workers`, sharing the wiring root, authenticated via
client-credentials. **Rationale:** keeps request latency bounded; ingestion is
inherently async (RAG returns a task_id).

### D-9 — Frontend editor foundation
The block editor is built on a ProseMirror-based rich-text core (e.g. TipTap)
bound to the Yjs doc via `y-prosemirror`; heavy blocks are custom node views:
KaTeX for `latex`, Mermaid for `mermaid`, a highlighter for `code`, an Excalidraw
canvas for `whiteboard`. ViewModels (`*.svelte.ts`) own editor state and agent
commands; Views (`*.svelte`) render; Models (`lib/api/*.ts`) are typed clients.
**Rationale:** ProseMirror+Yjs is the mature multiplayer rich-text stack; keeps
MVVM boundaries clean. **Alternative rejected:** hand-rolled contenteditable —
too costly to make collaborative and correct.

## Risks / Trade-offs

- CRDT + rich embeds (whiteboard, tables) is complex → start with a small block
  set behind the CRDT, add block types incrementally; cover convergence with
  BDD tests per layer (as Tessera does).
- External MCP servers are untrusted input → sandbox tool exposure, per-session
  opt-in, encrypt credentials, namespace tools, and cap tool-call fan-out.
- RAG ingestion latency/failure → treat as async tasks with visible status and
  retries; never block the editor on ingestion.
- Provider-agnostic LLM hides capability differences (tool-calling formats) →
  normalize tool-calling in the adapter, feature-detect per provider.
- Permission drift across three inbound surfaces → enforce in use cases only;
  add contract-parity tests asserting HTTP, realtime, and MCP deny identically.

## Migration Plan

Greenfield — no migration. Rollout order: auth-integration → document-model →
realtime-collaboration → block-editor → whiteboard-canvas → rag-knowledge →
ai-agent → mcp-server → external-mcp-connectors → permissions-sharing (permission
checks are wired in from document-model onward, hardened last).

## Open Questions

- Exact CRDT snapshot/compaction cadence and update-log retention window.
- Whether whiteboard scenes are Yjs subdocuments or an embedded shared type.
- Default LLM model/provider for production, and per-workspace model overrides.
- Comment storage: inside the CRDT vs a relational side table (leaning
  relational for query/notification).
