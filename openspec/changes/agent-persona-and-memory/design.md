# Design — Agent persona and persistent memory

## Context

The agent system prompt is a module-level constant assembled per run in
`AgentUseCases.ask()` (`use_cases/agent.py`), where the first `LLMMessage` is
`role="system"`. There is no stored persona or memory today. This change adds two
tenant-isolated stores and injects them at that seam, following the existing
hexagonal wiring (`_Repositories` dataclass, `_memory_repositories()`,
`_postgres_repositories()`, `_build_use_cases`, `UseCases`, mirrored in
`tests/conftest.py`).

## Decisions

### D-1 Scopes: workspace-first, optional personal layer

- **Custom instructions** are keyed by `(tenant_id, workspace_id)` for the shared
  house style, plus an optional `(tenant_id, workspace_id, user_id)` personal row.
  At injection the layers stack: `system prompt + workspace instructions +
  personal instructions (caller only)`. Workspace instructions are visible to the
  whole workspace; a personal layer is private to its author.
- **Memory** is scoped to `(tenant_id, workspace_id)` — a shared workspace brain,
  matching how RAG knowledge is already workspace-scoped. (A per-user memory scope
  is possible later via an optional `user_id` column but is out of scope for v1 to
  keep recall and management simple.)

Rationale: workspace scope mirrors the existing RAG/knowledge boundary and the
document ACL; it is the unit a team already reasons about. Personal instructions
cover the "just me" case without a second memory store.

### D-2 Permissions

- Setting/clearing **workspace** custom instructions requires
  `require_workspace(caller, workspace_id, Role.EDITOR)` (owners qualify — the
  role ladder is VIEWER<COMMENTER<EDITOR<OWNER). Reading them requires VIEWER.
- **Personal** instructions are read/written only by their author (no elevated
  role needed) and never surface to other users.
- **Memory**: reading/injecting requires VIEWER on the workspace; the `remember`
  tool and manual create/edit require EDITOR; deleting a memory requires EDITOR
  (or the memory's author). All checks go through `AccessControl`, never
  path/body trust. Every query is filtered by `caller.tenant_id`.

### D-3 Memory selection for injection (keep v1 simple)

On each `ask()` the use case selects a bounded set of memories to inject:

1. Take the N most recent memories for the workspace (recency), AND
2. Add memories whose text keyword-matches the user's instruction (case-folded
   token overlap), deduplicated,
3. Cap the merged set to a token budget (see D-4), newest first.

This needs no embedding infrastructure and is deterministic (testable with the
in-memory fake). **Future:** RAG-based semantic recall — store memories in the
workspace RAG project (or a dedicated embedding column) and retrieve by vector
similarity. The port is shaped so a `relevant(workspace_id, query, limit)` method
can later be backed by RAG without changing the use case's call site.

### D-4 Token budget

Injected persona+memory is capped so it cannot crowd out the document context.
Budget (config-tunable, defaults):

- Workspace custom instructions: max 4000 chars, truncated with an ellipsis.
- Personal instructions: max 2000 chars.
- Memories: up to 20 items or ~2000 chars total, whichever is hit first;
  overflow is dropped oldest-first from the recency set (keyword matches kept).

Instructions and memories are rendered as clearly delimited sections appended
after the base system prompt so the model can distinguish house rules from
recalled facts.

### D-5 Safety: no secrets in memory

- The `remember` tool description instructs the model to store durable
  preferences/facts, never secrets, tokens, passwords, or PII-heavy content.
- A lightweight guard rejects memory writes that match obvious secret patterns
  (e.g. `sk-`, `AKIA`, `-----BEGIN`, long high-entropy tokens, `password=`); the
  tool returns an error the model can relay instead of persisting.
- Delegated access tokens are never written to memory (they are already never
  logged; the memory path has no access to them).
- Memory text is stored as plain workspace data under tenant RLS; it is not sent
  to external MCP connectors.

### D-6 Migration shape

`db/migrations/0012_agent_persona_memory.sql`, next after `0011_templates.sql`,
applied by `scripts/migrate.py`. Two tables, both with tenant RLS
`tenant_id = current_setting('cyberarche.tenant_id', TRUE)`, mirroring the
`templates` table:

- `agent_custom_instructions(id, tenant_id, workspace_id FK→workspaces ON DELETE
  CASCADE, user_id NULL, instructions TEXT, updated_by, updated_at)` with a unique
  constraint on `(tenant_id, workspace_id, user_id)` (NULL user_id = the shared
  workspace layer) so upsert replaces in place.
- `agent_memories(id, tenant_id, workspace_id FK→workspaces ON DELETE CASCADE,
  text TEXT, created_by, created_at, updated_at)` indexed by
  `(tenant_id, workspace_id, created_at DESC)` for recency selection.

Both `ENABLE ROW LEVEL SECURITY` with a `*_tenant_isolation` policy.

### D-7 Injection seam

`ask()` builds `messages[0]` from `_SYSTEM_PROMPT + persona_sections`, where
`persona_sections` is produced by the new `AgentPersonaUseCases.build_context(
caller, workspace_id, instruction)` returning the instruction text and the
selected memories already within budget. The document's `workspace_id` is already
available in `ask()`. Keeping the assembly in a helper keeps `ask()` within the
backend cognitive-complexity target. The `remember`/`forget` tools are registered
in the agent's `ToolRegistry` and dispatch to the persona use case, so they are
permission-scoped via the caller like every other tool.

## Risks / trade-offs

- Keyword recall can miss paraphrased matches — accepted for v1; RAG recall is the
  named follow-up.
- Shared workspace memory means one user's saved note is visible to co-members —
  intended (shared brain), and bounded by the workspace ACL; personal preferences
  belong in personal instructions, not memory.
- Token budget may truncate long house styles — surfaced in the settings UI with a
  character counter.
