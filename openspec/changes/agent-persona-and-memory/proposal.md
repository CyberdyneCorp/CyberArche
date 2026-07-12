# Agent persona and persistent memory

## Why

Notion's Agent lets a workspace shape its assistant with custom instructions and
carries persistent memory across conversations. CyberArche's agent has neither:
the system prompt is a hard-coded constant (`_SYSTEM_PROMPT` in
`use_cases/agent.py`) and nothing survives a run — every conversation starts
cold. Teams cannot set a house style ("always cite sources", "answer in
Portuguese", "we are a Solidity shop"), and the agent re-learns the same facts
every time. This change adds two stored, tenant-isolated capabilities and injects
them into the agent's context.

## What Changes

- **Custom instructions** — per-workspace instructions (editable by workspace
  owners/editors) that shape the agent's tone/behavior, prepended to the system
  prompt on every run. An optional per-user personal-instructions layer stacks on
  top of the workspace layer for the calling user only.
- **Persistent memory** — durable notes scoped to a workspace (and tenant). The
  agent gets a `remember(note)` tool to save a memory during a run; relevant
  memories are selected and injected into context on later runs. A `forget` /
  list capability lets the agent and users manage them. Users can view, edit, and
  delete memories from a settings surface.
- **Data model** — new migration `0012_agent_persona_memory.sql` adding
  `agent_custom_instructions` and `agent_memories` tables, both with tenant RLS.
- **Injection** — the agent use case loads workspace + personal instructions and
  relevant memories in `ask()` and prepends them to the system prompt, within a
  fixed token budget.
- **Permissions** — only workspace owners/editors may set/clear custom
  instructions; memory read/write/delete is workspace-scoped and access-checked;
  nothing crosses tenants.
- **Frontend** — an agent settings surface (SvelteKit + Svelte 5 runes, MVVM) to
  edit custom instructions and to view/edit/delete memories.

## Impact

- Affected specs: `ai-agent` (ADDED: custom instructions, persistent memory).
- Affected code:
  - `db/migrations/0012_agent_persona_memory.sql` (new), applied by
    `scripts/migrate.py`.
  - `application/ports/agent_memory.py` (new port: instructions + memory
    repositories and domain records).
  - `domain/` new types (custom-instruction and memory records/ids).
  - `application/use_cases/agent_persona.py` (new use case) and injection changes
    in `use_cases/agent.py` (`ask()` + a new `remember`/`forget` tool).
  - `adapters/outbound/postgres/agent_memory.py` (Postgres repo) and
    `application/testing/` in-memory fakes.
  - Wiring: `_Repositories`, `_memory_repositories()`, `_postgres_repositories()`,
    `_build_use_cases`, `UseCases`, and `tests/conftest.py` mirror.
  - `adapters/inbound/http/routers/agent_persona.py` (new router).
  - Frontend agent-settings View/ViewModel/Model.
- Access is enforced from verified token claims; no path/body tenant trust.
