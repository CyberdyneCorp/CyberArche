# Tasks

## 1. Data model (migration)

- [ ] 1.1 Add `db/migrations/0012_agent_persona_memory.sql` (next after 0011)
  creating `agent_custom_instructions` and `agent_memories`.
- [ ] 1.2 `agent_custom_instructions`: `(id, tenant_id, workspace_id FK→workspaces
  ON DELETE CASCADE, user_id NULL, instructions, updated_by, updated_at)` with a
  unique constraint on `(tenant_id, workspace_id, user_id)` for upsert.
- [ ] 1.3 `agent_memories`: `(id, tenant_id, workspace_id FK→workspaces ON DELETE
  CASCADE, text, created_by, created_at, updated_at)` + index
  `(tenant_id, workspace_id, created_at DESC)`.
- [ ] 1.4 Enable RLS + `*_tenant_isolation` policy
  (`tenant_id = current_setting('cyberarche.tenant_id', TRUE)`) on both tables.
- [ ] 1.5 Confirm `scripts/migrate.py` applies 0012.

## 2. Domain

- [ ] 2.1 Add ids (`CustomInstructionsId`, `AgentMemoryId`) to `domain/ids.py`.
- [ ] 2.2 Add domain records `CustomInstructions` and `AgentMemory` (frozen,
  slots) with tenant/workspace/user fields and timestamps.
- [ ] 2.3 Add the secret-pattern guard helper (D-5) as a pure domain function.

## 3. Port

- [ ] 3.1 Add `application/ports/agent_memory.py` with
  `CustomInstructionsRepository` and `AgentMemoryRepository` Protocols.
- [ ] 3.2 Instructions repo: `get(tenant, workspace, user_id|None)`,
  `upsert(record)`, `clear(tenant, workspace, user_id|None)`.
- [ ] 3.3 Memory repo: `add(memory)`, `list_for_workspace(tenant, workspace)`,
  `recent(tenant, workspace, limit)`, `relevant(tenant, workspace, query, limit)`
  (keyword v1; RAG-swappable later), `get`, `update`, `delete`.

## 4. Repositories

- [ ] 4.1 `adapters/outbound/postgres/agent_memory.py`: Postgres impls of both
  repos, tenant-scoped, using the RLS session setting.
- [ ] 4.2 In-memory fakes in `application/testing/`
  (`InMemoryCustomInstructionsRepository`, `InMemoryAgentMemoryRepository`),
  exported from the testing package.

## 5. Use case

- [ ] 5.1 Add `application/use_cases/agent_persona.py` (`AgentPersonaUseCases`):
  get/set/clear workspace + personal instructions, and list/create/edit/delete
  memories — each with the `AccessControl` checks from D-2.
- [ ] 5.2 `build_context(caller, workspace_id, instruction)` selecting memories
  (recency + keyword, D-3) within the token budget (D-4) and returning rendered
  persona sections.
- [ ] 5.3 Enforce the secret guard (D-5) on every memory write.

## 6. Agent-prompt injection

- [ ] 6.1 In `use_cases/agent.py` `ask()`, prepend workspace + personal
  instructions and selected memories to the system prompt via
  `AgentPersonaUseCases.build_context`, keeping `ask()` within complexity target.
- [ ] 6.2 Render instructions and memories as delimited sections after
  `_SYSTEM_PROMPT`.

## 7. Permission checks

- [ ] 7.1 Workspace instructions: EDITOR to set/clear, VIEWER to read.
- [ ] 7.2 Personal instructions: author-only read/write.
- [ ] 7.3 Memory: VIEWER to read/inject, EDITOR to write, EDITOR-or-author to
  delete; every query filtered by `caller.tenant_id`.

## 8. Memory tool (remember / forget)

- [ ] 8.1 Register a `remember(note)` tool in the agent `ToolRegistry` that saves
  a workspace memory (EDITOR-checked) and returns confirmation.
- [ ] 8.2 Register a `forget`/list capability (list recent memories; delete by id)
  scoped to the workspace.
- [ ] 8.3 Tool descriptions instruct: store durable facts/preferences, never
  secrets/tokens/PII.

## 9. HTTP router

- [ ] 9.1 Add `adapters/inbound/http/routers/agent_persona.py`: GET/PUT/DELETE
  workspace + personal instructions; GET/POST/PATCH/DELETE memories.
- [ ] 9.2 Register the router in `routers/__init__.py`; DomainError→HTTP via the
  existing seam.

## 10. Wiring

- [ ] 10.1 Add the two repos to the `_Repositories` dataclass.
- [ ] 10.2 Construct fakes in `_memory_repositories()` and Postgres impls in
  `_postgres_repositories()`.
- [ ] 10.3 Build `AgentPersonaUseCases` in `_build_use_cases`, inject it into
  `AgentUseCases`, and expose it on the `UseCases` container.
- [ ] 10.4 Mirror the additions in `tests/conftest.py`.

## 11. Frontend (SvelteKit + Svelte 5 runes, MVVM)

- [ ] 11.1 Model: typed HTTP client under `lib/api/` for instructions + memories.
- [ ] 11.2 ViewModel (`*.svelte.ts`, `$state`/`$derived`, singleton + factory).
- [ ] 11.3 View: agent-settings surface — edit custom instructions (with a
  character counter) and view/edit/delete memories; personal-instructions field
  gated to the current user.

## 12. Tests

- [ ] 12.1 Instructions injected into the prompt on `ask()`.
- [ ] 12.2 Only owners/editors may set workspace instructions; viewers denied;
  personal instructions private to author.
- [ ] 12.3 `remember` saves a memory; a later run recalls it in context.
- [ ] 12.4 Memory is tenant/workspace scoped — never leaks across tenants.
- [ ] 12.5 User can delete a memory; deleted memory no longer injected.
- [ ] 12.6 Secret-pattern write is rejected.
- [ ] 12.7 Router happy/deny paths.

## 13. Spec / docs

- [ ] 13.1 `openspec validate agent-persona-and-memory --strict` passes.
- [ ] 13.2 Update `openspec/project.md` / any agent docs if behavior notes change.
