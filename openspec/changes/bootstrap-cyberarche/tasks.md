## 1. Repo & Composition Scaffolding

- [x] 1.1 Create monorepo layout: `libs/cyberarche/{domain,application,adapters}`, `services/cyberarche/{api,mcp,workers}`, `apps/cyberarche/web`
- [x] 1.2 Configure Python workspace (pyproject), FastAPI, FastMCP, pycrdt, LiteLLM/Anthropic SDK, and import-linter with the hexagonal dependency contract
- [x] 1.3 Add the `wiring/` composition root building a `Container` (ports → adapters), consumed by all three services
- [x] 1.4 FastAPI factory: `Container` on `app.state`, `Caller`/`Cases` DI, single DomainError→HTTP seam, CORS + observability
- [ ] 1.5 Scaffold SvelteKit + Svelte 5 web app with MVVM folders (`lib/components`, `lib/viewmodels` `.svelte.ts`, `lib/api`, `lib/data`, `lib/crdt`)
- [x] 1.6 Provision Postgres schema migrations (documents, blocks/snapshots, crdt_updates, memberships, share_grants, agent_runs, mcp_connectors) with RLS

## 2. Auth Integration (auth-integration)

- [ ] 2.1 Register CyberArche as a CyberdyneAuth OAuth client; store client config
- [x] 2.2 `TokenPort`/`AuthProviderPort` + adapter: verify JWT via JWKS, introspect for opaque/service tokens; cache JWKS
- [x] 2.3 `require_caller` builds `CallerContext(user_id, tenant_id, roles)` from claims only; 401 seam before use cases
- [x] 2.4 Client-credentials adapter for worker/service-to-service tokens
- [x] 2.5 IAM authorization: delegate policy evaluation to CyberdyneAuth `iam/evaluate` behind an `AuthorizationPort`
- [ ] 2.6 Web: OIDC auth-code + PKCE sign-in flow, session handling, `lib/api/auth.ts`, auth ViewModel
- [x] 2.7 BDD tests: reject invalid/expired token, tenant-not-spoofable, worker gets service token

## 3. Document Model (document-model)

- [x] 3.1 Domain: `Workspace`, `Document`, `Block`, `Membership`, value objects and invariants (block-type whitelist, hierarchy)
- [x] 3.2 Ports: `WorkspaceRepository`, `DocumentRepository`, `SnapshotRepository` (+ in-memory fakes)
- [x] 3.3 Use cases: create/list/move workspace & document, reorder children, soft-delete/restore, snapshot list/restore
- [x] 3.4 Postgres adapters for the repositories with tenant RLS
- [x] 3.5 HTTP routers: workspaces, documents (CRUD, move, trash/restore), snapshots
- [ ] 3.6 Web: workspace sidebar + document tree Views/ViewModels; `lib/api/documents.ts`, `lib/data/workspace.ts`
- [x] 3.7 BDD tests: nesting/reorder, tenant isolation, trash+restore, snapshot restore

## 4. Realtime Collaboration (realtime-collaboration)

- [x] 4.1 `CrdtEnginePort` + pycrdt adapter: authoritative doc, apply/update, snapshot/compaction
- [x] 4.2 FastAPI WebSocket relay: auth handshake, join-authorization, update broadcast, awareness/presence fanout
- [x] 4.3 Persist update log + periodic snapshot; reconstruct document on reconnect/restart
- [x] 4.4 Enforce view/edit permission on join and on every inbound update
- [ ] 4.5 Web: Yjs client, WebSocket provider, offline persistence + reconnect merge; presence/cursor rendering
- [x] 4.6 BDD tests: two-editor convergence, late joiner catch-up, reconstruct after restart, reject view-only editor, offline merge

## 5. Block Editor (block-editor)

- [ ] 5.1 Web: ProseMirror/TipTap core bound to Yjs (`y-prosemirror`); base blocks (paragraph, heading, lists, todo, callout, quote, divider)
- [ ] 5.2 Slash command menu + Markdown-style input shortcuts
- [ ] 5.3 `code` block with language selection + syntax highlighting
- [ ] 5.4 `latex` block with KaTeX live render + source preservation + inline error
- [ ] 5.5 `mermaid` block with render + source preservation + parse-error display
- [ ] 5.6 `table` block: rich-text cells, add/remove row & column
- [ ] 5.7 Editor ViewModel (`active-editor.svelte.ts`) exposing commands + undo/redo
- [ ] 5.8 Tests: slash insert, split/merge, LaTeX/Mermaid render + error, table row/column ops, heading shortcut

## 6. Whiteboard Canvas (whiteboard-canvas)

- [ ] 6.1 Web: `whiteboard` block embedding an Excalidraw-style canvas, scene stored in the document CRDT
- [ ] 6.2 Canvas primitives (rect/ellipse/diamond/arrow/freehand/text/image) with styling and bound connectors
- [ ] 6.3 Mind-map support: node/branch model, manual add-child
- [ ] 6.4 Collaborative canvas editing merged via the document CRDT
- [ ] 6.5 Tests: persistence/restore, bound arrow follows shape, concurrent shape edits converge

## 7. RAG Knowledge (rag-knowledge)

- [x] 7.1 `RagPort` + CyberdyneRAG adapter (project create, upload, task poll/callback, query, datasource delete)
- [x] 7.2 Provision an isolated RAG `project_slug` on workspace creation
- [x] 7.3 Ingestion use case: upload file, track task to completion, dedupe; wire to workers
- [x] 7.4 Retrieval use case: query with mode (local/global/hybrid/naive/mix)
- [x] 7.5 Delete-source cascade to RAG datasource
- [x] 7.6 Webhook endpoint for RAG task completion (verify secret)
- [x] 7.7 BDD tests: provision on create, cross-workspace isolation, track-to-completion, dedupe, delete cascade

## 8. AI Agent (ai-agent)

- [x] 8.1 `LLMPort` + adapters (Anthropic/OpenAI/local via LiteLLM), config-selected; normalized tool-calling
- [x] 8.2 Domain/use cases: document-scoped agent context (blocks + RAG), summarize, draft/rewrite selection
- [x] 8.3 Agent applies edits through `CrdtEnginePort` as a peer (attributed, live)
- [x] 8.4 File ingestion into blocks: PDF→blocks, CSV/Excel→`table` blocks; submit to RAG (worker job)
- [x] 8.5 Agent tool-use loop calling CyberArche MCP + external MCP tools, permission-scoped
- [x] 8.6 `AgentRun` recording (prompt, tools, docs touched, model, outcome)
- [ ] 8.7 Web: agent panel View/ViewModel, insert-as-blocks, run history
- [x] 8.8 BDD tests: grounded answer with citations, live agent edit merges, PDF ingest, spreadsheet→table, run auditing

## 9. MCP Server (mcp-server)

- [x] 9.1 `services/cyberarche/mcp` FastMCP deployable on the shared composition root
- [x] 9.2 Token-auth on tool calls; resolve `CallerContext`; enforce permissions/tenant in use cases
- [x] 9.3 Document tools: search, read, create, edit (via CRDT)
- [x] 9.4 Knowledge tools: ingest file, RAG query
- [x] 9.5 Contract-parity tests: HTTP, realtime, and MCP deny identically; unauthorized read denied; tenant scoping

## 10. External MCP Connectors (external-mcp-connectors)

- [x] 10.1 `McpClientPort` + adapter to connect/handshake external MCP servers
- [x] 10.2 Connector registration use case (scope, endpoint, encrypted credentials), reject unreachable
- [x] 10.3 Envelope-encrypt credentials at rest; never return secrets
- [x] 10.4 Namespace external tools by connector; expose origin to the agent
- [x] 10.5 Per-session enable/disable; only enabled connectors' tools offered
- [x] 10.6 Tests: add/reject connector, secrets not readable, namespaced collision, disable removes tools

## 11. Permissions & Sharing (permissions-sharing)

- [x] 11.1 Domain: roles (owner/editor/commenter/viewer), workspace→document inheritance + override
- [x] 11.2 Invite use case (by CyberdyneAuth identity) with role
- [x] 11.3 Share links scoped to view/comment/edit, revocable + expiring
- [x] 11.4 `ShareGrant`/membership repositories + Postgres adapters
- [x] 11.5 Comments on blocks (add/resolve), storage + fanout
- [x] 11.6 Enforce checks uniformly in use cases (HTTP + realtime + MCP)
- [ ] 11.7 Web: share dialog, invite UI, comment thread View/ViewModel
- [x] 11.8 BDD tests: inheritance + override, invite-as-commenter, view-link open/revoke, consistent denial across surfaces

## 12. Architecture Quality (architecture-quality)

- [ ] 12.1 Block-type registry: add a block type via registration only (render/serialize), no core-editor edits; back-compat load test
- [ ] 12.2 Port/adapter seams verified for every provider (LLM, RAG, auth, storage, CRDT); config-driven selection
- [ ] 12.3 Shared contract-test suites per port; run every real and fake adapter against them
- [ ] 12.4 Make API and MCP stateless (no in-process shared state); horizontal-replica test with no sticky sessions
- [ ] 12.5 Multi-instance realtime relay sharing CRDT state via update log + broker (e.g. Redis pub/sub); cross-instance convergence test
- [ ] 12.6 Queue-backed workers for ingestion and large agent runs; assert requests/editor never block

## 13. Validation & CI

- [ ] 13.1 `openspec validate --all --strict` in CI
- [ ] 13.2 import-linter boundary check in CI (domain ← application ← adapters); fail on violation
- [ ] 13.3 Backend pytest (incl. BDD + contract-parity) + frontend Vitest/Playwright gates
- [ ] 13.4 Cognitive-complexity gate (backend ≤15, frontend 8–12) on changed files
