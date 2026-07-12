# Saved agent skills

## Why

Users repeatedly type the same agent instructions — "write a weekly status
summary", "turn this doc into an FAQ", "extract action items as a checklist".
Notion's Agent lets people save named, reusable prompts ("skills") and re-run
them on demand. CyberArche has no equivalent: every run starts from a blank
prompt. Saving a named, parameterized instruction once and invoking it from the
agent panel is a small, high-utility win that makes the agent feel like a
teammate with a repertoire.

This is distinct from **page templates** (the `templates` capability), which
capture DOCUMENT block content. A skill captures an AGENT INSTRUCTION, not a
document. It reuses the templates pattern (workspace-scoped, shareable, its own
table and repository) but produces prompt text, not blocks.

## What Changes

- Add **saved agent skills** to the `ai-agent` capability: a workspace has named
  reusable agent instructions, each with an optional short description and an
  instruction template that may contain simple `{variables}`.
- **Save a skill**: an authorized member saves a named skill with its
  instruction template (and declared variables) in the workspace.
- **Invoke a skill**: from the agent panel, a member picks a skill, fills any
  variables, and the system expands the template into a concrete instruction
  string and runs it through the existing agent `ask()` tool-loop against the
  current document/workspace. No new agent-loop mechanics — a skill only
  produces the instruction text.
- **Manage skills**: list the workspace's skills, and update or delete a skill.
- Skills are **workspace/tenant scoped and shareable** with the workspace: all
  members may list and run them; owners/editors may create, edit, and delete.

## Impact

- Affected spec: `ai-agent` (new requirement: *Saved agent skills*).
- Data model: new `agent_skills` table (migration
  `db/migrations/0013_agent_skills.sql`) with tenant RLS. Numbered after
  `0011_templates.sql` and the in-flight `agent-persona-and-memory` change
  (which is expected to claim `0012`); see `design.md` for the ordering note.
- Affected backend code (Hexagonal, no code in this change — described in
  `tasks.md`): new `AgentSkill` domain type; `AgentSkillRepository` port
  (`application/ports/agent_skills.py`) with Postgres adapter + in-memory fake;
  `AgentSkillUseCases` (save, list, update, delete, and `instantiate` =
  variable expansion → instruction string); an HTTP router; container wiring and
  `tests/conftest.py` wiring, mirroring the `templates` capability.
- Frontend (SvelteKit + Svelte 5 runes, no code in this change): a typed
  `api/agentSkills` client, a skill picker in the agent panel that fills
  variables and sends the expanded instruction to the existing agent `ask`
  flow, and a small management surface to create/edit/delete skills.
- Access: workspace members may list/run skills; creating, editing, and
  deleting require editor (or owner) rights, consistent with `templates`.
