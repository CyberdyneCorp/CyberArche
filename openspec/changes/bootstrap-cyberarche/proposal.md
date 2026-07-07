## Why

Teams need a Notion/Confluence alternative that treats technical content (math,
diagrams, whiteboards, code, tables) and AI as first-class rather than
bolted-on. Existing tools bury LaTeX/Mermaid behind plugins, have no native
whiteboard, and expose AI only as a side chat with no access to your documents.
CyberArche is AI-centric and MCP-native from day one: every document has an
agent that can read, draft, restructure, and ingest files, grounded in the
workspace via RAG, and both humans and agents collaborate live via CRDT.

This change bootstraps the platform: the full vertical foundation (data model,
editor, whiteboard, realtime collaboration, AI agent, MCP server, external MCP
connectors, CyberdyneAuth SSO, CyberdyneRAG ingestion, and permissions/sharing).

## What Changes

- **New backend** in Hexagonal Architecture (FastAPI + FastMCP) with a
  provider-agnostic LLM port and outbound adapters for CyberdyneAuth,
  CyberdyneRAG, PostgreSQL, object storage, and a Yjs/CRDT engine.
- **New frontend** (Svelte 5 + SvelteKit, strict MVVM) — a block-based document
  editor with slash menu, LaTeX/Mermaid/code/table blocks, and a native
  Excalidraw-style whiteboard block (with mind-map support).
- **Realtime multiplayer** via Yjs over a FastAPI WebSocket relay: live cursors,
  presence, offline editing, conflict-free merge; the AI agent applies edits as
  a CRDT peer.
- **AI document agent**: summarize, draft, restructure, Q&A, and ingest
  PDF/CSV/Excel (tables) into documents — grounded by RAG retrieval.
- **FastMCP server** exposing tools over the caller's own and shared documents
  (search, read, create, edit, ingest, RAG query); OAuth-protected.
- **External MCP connectors**: users attach their own MCP servers so the agent
  can call additional tools within a document session.
- **CyberdyneAuth SSO** (OIDC/OAuth2, JWT via JWKS) with IAM-driven authz and
  **BREAKING**-free tenant scoping from verified token claims.
- **CyberdyneRAG integration**: each workspace maps to an isolated RAG project;
  documents and uploads are ingested and made retrievable.
- **Permissions & sharing**: document/workspace ACL, roles, invites, and
  shareable links (view/comment/edit).

## Capabilities

### New Capabilities

- `document-model`: documents, workspaces/folders, block tree, version snapshots.
- `block-editor`: block-based editing — text/headings/lists/callouts, slash
  menu, tables, code, LaTeX math, and Mermaid diagram blocks.
- `whiteboard-canvas`: native Excalidraw-style canvas block, including mind maps.
- `realtime-collaboration`: Yjs/CRDT sync, presence, live cursors, offline merge.
- `ai-agent`: per-document AI assistant — summarize/draft/restructure/ingest,
  editing the doc as a CRDT peer, grounded via RAG, over a provider-agnostic LLM.
- `mcp-server`: FastMCP server exposing document + RAG tools, OAuth-protected.
- `external-mcp-connectors`: attach external MCP servers to an agent session.
- `auth-integration`: CyberdyneAuth OIDC/OAuth2 SSO, JWT verification, IAM authz.
- `rag-knowledge`: CyberdyneRAG project mapping, file ingestion, retrieval.
- `permissions-sharing`: document/workspace ACL, roles, invites, share links.

### Modified Capabilities

_None — greenfield project; no existing specs._

## Impact

- **Domain** `libs/cyberarche/domain`: Document, Block, Workspace, Membership,
  ShareGrant, AgentRun aggregates and value objects.
- **Application** `libs/cyberarche/application`: ports (`DocumentRepository`,
  `LLMPort`, `RagPort`, `AuthProviderPort`/`TokenPort`, `CrdtEnginePort`,
  `McpToolRegistryPort`, `BlobStoragePort`) + use cases per capability + fakes.
- **Adapters** `libs/cyberarche/adapters`: inbound `http/` (FastAPI routers) &
  `mcp/` (FastMCP tools); outbound `postgres/ rag/ auth/ crdt/ llm/ objectstore/`;
  `wiring/` composition root.
- **Services** `services/cyberarche/{api,mcp,workers}`: three deployables sharing
  one composition root.
- **Web** `apps/cyberarche/web`: editor, whiteboard, agent panel, share dialog,
  CRDT client, typed API clients (MVVM).
- **External**: CyberdyneAuth (OAuth client registration, JWKS), CyberdyneRAG
  (per-workspace project provisioning). New deps: FastMCP, pycrdt/Yjs, LiteLLM
  (or Anthropic SDK), a Mermaid renderer, a LaTeX (KaTeX) renderer, Excalidraw.
- **Data**: new PostgreSQL schema (documents, blocks/snapshots, CRDT update log,
  memberships, share grants, agent runs, MCP connector configs).
