# Tasks

## 1. Data model
- [x] 1.1 Migration `db/migrations/0013_agent_skills.sql` creating `agent_skills`
  (id, tenant_id, workspace_id, name, description, instruction, variables jsonb,
  created_by, created_at) with an index on `(tenant_id, workspace_id)`
- [x] 1.2 Enable RLS with policy
  `tenant_id = current_setting('cyberarche.tenant_id', TRUE)`
- [x] 1.3 Confirm `0012` is left for `agent-persona-and-memory`; keep this at
  `0013` (see design.md ordering note)

## 2. Domain
- [x] 2.1 `AgentSkill` domain type (name, description, instruction, variables)
  in `domain/agent_skills.py`
- [x] 2.2 `AgentSkillId` id type in `domain/ids.py`
- [x] 2.3 Pure helper: parse `{variable}` names from an instruction; expand a
  template with a values map (empty for missing, leave unknown braces verbatim)

## 3. Port + repositories
- [x] 3.1 `AgentSkillRepository` port in
  `application/ports/agent_skills.py` (add, list_for_workspace, get, update,
  delete) mirroring `ports/templates.py`
- [x] 3.2 `InMemoryAgentSkillRepository` fake in `application/testing`
- [x] 3.3 Postgres adapter in `adapters/outbound/postgres`, tenant-scoped

## 4. Use case
- [x] 4.1 `AgentSkillUseCases` in `application/use_cases/agent_skills.py`:
  `save` (EDITOR), `list` (VIEWER), `update` (EDITOR), `delete` (creator or OWNER)
- [x] 4.2 `instantiate(caller, skill_id, values)` → instruction string:
  expand declared `{variables}`; pure, no LLM call
- [x] 4.3 Enforce workspace/tenant scoping and role checks in every method

## 5. Wiring
- [x] 5.1 Register `AgentSkillUseCases` in the container composition root
  (mirror the `templates` wiring)
- [x] 5.2 Add wiring to `tests/conftest.py` with `InMemoryAgentSkillRepository`

## 6. HTTP router
- [x] 6.1 `routers/agent_skills.py`: `POST /workspaces/{id}/agent-skills`,
  `GET /workspaces/{id}/agent-skills`,
  `POST /workspaces/{id}/agent-skills/{sid}/instantiate` (returns the expanded
  instruction), `PATCH /agent-skills/{sid}`, `DELETE /agent-skills/{sid}`
- [x] 6.2 Thin router: delegate to the use case; auth/tenant from token claims

## 7. Frontend (SvelteKit + Svelte 5 runes)
- [x] 7.1 Typed `lib/api/agentSkills` client returning skill DTOs
- [x] 7.2 Agent-panel skill picker: list skills, show name/description, collect
  variable values, then send the expanded instruction to the existing agent
  `ask` flow (no new agent mechanics)
- [x] 7.3 Skill management surface (create / edit / delete), gated to
  editors/owners in the UI
- [x] 7.4 ViewModel (`*.svelte.ts`) owning skill state; View never calls the API
  directly

## 8. Permission checks
- [x] 8.1 List/run require workspace membership (VIEWER)
- [x] 8.2 Create/edit require EDITOR; delete requires creator or OWNER
- [x] 8.3 Running a skill respects the caller's document/workspace permissions via
  the existing `ask()` path (a skill cannot widen access)

## 9. Tests
- [x] 9.1 Use-case tests: save persists; list scoped to workspace/tenant;
  update; delete by creator and by owner; non-authorized delete rejected
- [x] 9.2 `instantiate` expands variables; missing value → empty; unknown brace
  left verbatim
- [x] 9.3 Permission tests: viewer cannot create/edit/delete; non-member cannot
  list; tenant isolation
- [x] 9.4 Router/integration test for the instantiate endpoint returning the
  instruction string

## 10. Spec + docs
- [x] 10.1 `openspec validate agent-saved-skills --strict` → zero errors
- [x] 10.2 Update `openspec/project.md` / capability notes if behavior docs change
- [x] 10.3 After implementation, archive the change so the `ai-agent` spec absorbs
  the new requirement
