# Design — Saved agent skills

## Context

Notion's Agent lets users save named, reusable prompts ("skills") and run them
on demand. We already have a close structural precedent: **page templates**
(`templates` capability — `domain/templates.py`, `ports/templates.py`,
`use_cases/templates.py`, `0011_templates.sql`, RLS, a router, and conftest
wiring). Agent skills reuse that shape but store an agent INSTRUCTION rather than
document blocks. Invocation folds onto the existing agent `ask()` flow, which
already accepts a plain `instruction: str`.

## Goals

- A skill is a named, reusable agent instruction, workspace-scoped and shareable.
- Invoking a skill produces a concrete instruction string and runs it through the
  normal agent tool-loop against the current document/workspace.
- No new agent-loop mechanics; no changes to how the model, tools, or CRDT edits
  work.

## Decisions

### Skill shape

An `AgentSkill` is:

- `id`, `tenant_id`, `workspace_id`, `created_by`, `created_at` — mirror
  `Template`.
- `name` — required, short, human-readable (e.g. "Weekly status summary").
- `description` — optional short blurb shown in the picker (e.g. "Summarize the
  doc's recent changes into a status update").
- `instruction` — the instruction template: free text that may contain
  `{variable}` placeholders (e.g. "Summarize this document as a status update
  for {audience}, focused on {topic}.").
- `variables` — the declared placeholder names (e.g. `["audience", "topic"]`),
  derived from the instruction and used to drive the fill-in form. Stored so the
  UI need not re-parse, and so a variable with no placeholder occurrence can
  still be prompted for if desired.

### Variable substitution syntax

Single-brace `{name}` placeholders, `name` matching `[a-zA-Z_][a-zA-Z0-9_]*`.
Expansion (`instantiate`) replaces each `{name}` with the caller-supplied value.
Rules:

- A placeholder with no supplied value is replaced with an empty string (the run
  still proceeds); the UI SHOULD collect all declared variables before sending.
- Unrecognized `{...}` that is not a declared variable is left verbatim, so
  instructions may contain literal braces without breaking.
- Substitution is a pure string operation with no evaluation or interpolation of
  document content — a skill only ever yields text.

### Scope and sharing

Skills are **workspace/tenant scoped**. Every skill row carries `tenant_id` and
`workspace_id`; the table has RLS
`tenant_id = current_setting('cyberarche.tenant_id', TRUE)`, identical to
`templates`. A skill is implicitly shared with the whole workspace: any member
may list and run it. There is no per-skill ACL beyond workspace membership in
this change.

### Permissions

Mirror `templates`:

- **List / run**: workspace `VIEWER` (any member).
- **Create / edit**: workspace `EDITOR`.
- **Delete**: the skill's creator, or a workspace `OWNER`.

Running a skill goes through the existing `ask()`, so it is additionally bound by
the caller's permissions on the current document/workspace — a skill cannot
widen access. A view-only caller can run a skill that only reads/answers, but any
document edit the agent attempts is still denied by the agent's own edit-permission
checks.

### Relationship to templates

Sibling pattern, separate table. `templates` stores block `content` (JSONB block
tree) and its use case writes blocks into a new document via the CRDT. `agent_skills`
stores an `instruction` (text) + `variables`, and its `instantiate` returns a
string. They share no rows and no code path; skills deliberately copy the
templates repository/use-case/wiring shape so the codebase stays uniform.

### Invocation maps onto `ask()`

`AgentUseCases.ask(caller, document_id, *, instruction, ...)` already takes a
plain instruction string. Invoking a skill is therefore:

1. Frontend picks a skill and collects variable values.
2. `AgentSkillUseCases.instantiate(skill_id, values)` expands the template into
   an instruction string (pure use case; no LLM).
3. The frontend sends that string to the existing agent `ask` endpoint exactly as
   if the user had typed it.

A skill is therefore nothing more than a saved, parameterized producer of the
`instruction` argument. No new tool, no new loop, no change to `ask()`.

## Migration ordering

The latest committed migration is `0011_templates.sql`. Two agent changes are in
flight against the `ai-agent` spec: `agent-persona-and-memory` (expected to add a
persona/memory table, claiming `0012`) and this change. To avoid a collision we
number this migration **`0013_agent_skills.sql`**, a clearly-later number that
leaves `0012` for `agent-persona-and-memory`. Migrations are additive and
independent (no shared tables), so apply order beyond "after 0011" does not
matter for correctness; the gap is purely to keep numbering monotonic if both
land. If `agent-persona-and-memory` does not ship a migration, `0013` remains
valid (a numbering gap is harmless).

## Risks / trade-offs

- **Variable form UX**: declared-but-unfilled variables expand to empty strings;
  the picker should validate to avoid sending half-empty instructions. Accepted:
  keeps the use case simple and the run always succeeds.
- **No versioning / history** for skills in this change; edits overwrite. Acceptable
  for a first cut; a future change can add revisions if needed.
- **No cross-workspace sharing**: intentional, matches `templates`.
