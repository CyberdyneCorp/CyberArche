# CyberArche — Project Context

## Purpose

CyberArche is an AI-centric, real-time collaborative document platform — a
Notion/Confluence alternative built around three differentiators:

1. **Rich technical blocks first-class**: LaTeX math, a native Excalidraw-style
   whiteboard (mind maps included), Mermaid diagrams, executable-looking code
   blocks with syntax highlighting, and tables.
2. **AI at the center**: every document has an AI agent that can summarize,
   draft, restructure, and ingest files (PDF/CSV/Excel). The agent edits the
   document as a first-class CRDT collaborator and is grounded in the workspace
   via RAG.
3. **MCP-native**: CyberArche ships its own FastMCP server exposing tools over
   the user's own and shared documents, and lets users attach external MCP
   servers so their agent gains extra capabilities.

## Tech Stack

- **Backend**: Python 3.12+, FastAPI (inbound HTTP), FastMCP (inbound MCP),
  Hexagonal Architecture. Package namespace `cyberarche.<context>.<layer>`.
- **Realtime**: Yjs/CRDT. A WebSocket relay in FastAPI persists binary updates
  and periodic JSON snapshots (pycrdt server-side).
- **Frontend**: Svelte 5 (runes) + SvelteKit + TypeScript, strict MVVM.
- **LLM**: provider-agnostic behind an `LLMPort` (Anthropic/OpenAI/local via
  config, e.g. LiteLLM). Default model targets the latest Claude models.
- **Persistence**: PostgreSQL (documents, metadata, ACL, CRDT update log +
  snapshots). Object storage for uploaded originals.

## External Services (owned by us)

- **CyberdyneAuth** — `https://auth.backend.coolify.cyberdynecorp.ai`
  OIDC/OAuth2 + JWT (RS256). We are an OAuth client; we verify tokens against
  `/.well-known/jwks.json`, use `/api/v1/auth/introspect` for opaque checks,
  read identity from `/api/v1/users/me`, and consume IAM policies/groups.
- **CyberdyneRAG** — `https://cyberrag.coolify.cyberdynecorp.ai`
  Per-`project_slug` isolated LightRAG workspaces. We ingest documents
  (`/documents/upload`), poll tasks, and query (`/queries/sync|async`, modes
  local/global/hybrid/naive/mix). Bearer-token authenticated.

## Architecture Conventions

### Backend — Hexagonal (mirrors `~/work/tessera`)

```
libs/<context>/domain/        # pure domain, zero I/O
libs/<context>/application/
    ports/                    # Protocols: repositories, llm, rag, auth, crdt, mcp, storage
    use_cases/                # one folder per capability
    testing/                  # in-memory fakes
libs/<context>/adapters/
    inbound/  http/ mcp/      # FastAPI routers + FastMCP tools (thin, delegate to use cases)
    outbound/ postgres/ rag/ auth/ crdt/ llm/ objectstore/
    wiring/                   # single composition root -> Container
services/<context>/api/       # FastAPI factory: Container on app.state, Caller/Cases DI
services/<context>/mcp/       # FastMCP deployable, same wiring/ composition root
services/<context>/workers/   # async ingestion/AI jobs, same wiring
```

Dependency rule: `domain <- application <- adapters`; inbound never imports
outbound. Enforced with import-linter. Auth/tenant scope comes from **verified
token claims**, never from path/body. DomainError→HTTP status via a single seam.

### Frontend — MVVM (Svelte 5 runes)

- **View** = `*.svelte` (routes `+page.svelte`, components in `lib/components/`).
- **ViewModel** = `*.svelte.ts` (uses `$state`/`$derived`; exported as a module
  singleton plus a `createXxx()` factory for tests).
- **Model** = plain `*.ts` under `lib/data/` and `lib/api/` (typed HTTP clients
  returning DTOs). Views never call the API directly — only through a ViewModel.

## Conventions

- Medium/large or auth/billing/security/data-model changes go through OpenSpec.
- Every bug fix ships a regression test in the same change.
- RFC-2119 language in specs (SHALL/MUST/MAY). Every requirement has ≥1 scenario.
- Backend cognitive complexity target ≤15 per function; frontend 8–12.
