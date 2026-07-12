# Tasks

## 1. Data model
- [ ] 1.1 Migration `db/migrations/0013_agent_skills.sql` creating `agent_skills`
  (id, tenant_id, workspace_id, name, description, instruction, variables jsonb,
  created_by, created_at) with an index on `(tenant_id, workspace_id)`
- [ ] 1.2 Enable RLS with policy
  `tenant_id = current_setting('cyberarche.tenant_id', TRUE)`
- [ ] 1.3 Confirm `0012` is left for `agent-persona-and-memory`; keep this at
  `0013` (see design.md ordering note)

## 2. Domain
- [ ] 2.1 `AgentSkill` domain type (name, description, instruction, variables)
  in `domain/agent_skills.py`
- [ ] 2.2 `AgentSkillId` id type in `domain/ids.py`
- [ ] 2.3 Pure helper: parse `{variable}` names from an instruction; expand a
  template with a values map (empty for missing, leave unknown braces verbatim)

## 3. Port + repositories
- [ ] 3.1 `AgentSkillRepository` port in
  `application/ports/agent_skills.py` (add, list_for_workspace, get, update,
  delete) mirroring `ports/templates.py`
- [ ] 3.2 `InMemoryAgentSkillRepository` fake in `application/testing`
- [ ] 3.3 Postgres adapter in `adapters/outbound/postgres`, tenant-scoped

## 4. Use case
- [ ] 4.1 `AgentSkillUseCases` in `application/use_cases/agent_skills.py`:
  `save` (EDITOR), `list` (VIEWER), `update` (EDITOR), `delete` (creator or OWNER)
- [ ] 4.2 `instantiate(caller, skill_id, values)` → instruction string:
  expand declared `{variables}`; pure, no LLM call
- [ ] 4.3 Enforce workspace/tenant scoping and role checks in every method

## 5. Wiring
- [ ] 5.1 Register `AgentSkillUseCases` in the container composition root
  (mirror the `templates` wiring)
- [ ] 5.2 Add wiring to `tests/conftest.py` with `InMemoryAgentSkillRepository`

## 6. HTTP router
- [ ] 6.1 `routers/agent_skills.py`: `POST /workspaces/{id}/agent-skills`,
  `GET /workspaces/{id}/agent-skills`,
  `POST /workspaces/{id}/agent-skills/{sid}/instantiate` (returns the expanded
  instruction), `PATCH /agent-skills/{sid}`, `DELETE /agent-skills/{sid}`
- [ ] 6.2 Thin router: delegate to the use case; auth/tenant from token claims

## 7. Frontend (SvelteKit + Svelte 5 runes)
- [ ] 7.1 Typed `lib/api/agentSkills` client returning skill DTOs
- [ ] 7.2 Agent-panel skill picker: list skills, show name/description, collect
  variable values, then send the expanded instruction to the existing agent
  `ask` flow (no new agent mechanics)
- [ ] 7.3 Skill management surface (create / edit / delete), gated to
  editors/owners in the UI
- [ ] 7.4 ViewModel (`*.svelte.ts`) owning skill state; View never calls the API
  directly

## 8. Permission checks
- [ ] 8.1 List/run require workspace membership (VIEWER)
- [ ] 8.2 Create/edit require EDITOR; delete requires creator or OWNER
- [ ] 8.3 Running a skill respects the caller's document/workspace permissions via
  the existing `ask()` path (a skill cannot widen access)

## 9. Tests
- [ ] 9.1 Use-case tests: save persists; list scoped to workspace/tenant;
  update; delete by creator and by owner; non-authorized delete rejected
- [ ] 9.2 `instantiate` expands variables; missing value → empty; unknown brace
  left verbatim
- [ ] 9.3 Permission tests: viewer cannot create/edit/delete; non-member cannot
  list; tenant isolation
- [ ] 9.4 Router/integration test for the instantiate endpoint returning the
  instruction string

## 10. Spec + docs
- [ ] 10.1 `openspec validate agent-saved-skills --strict` → zero errors
- [ ] 10.2 Update `openspec/project.md` / capability notes if behavior docs change
- [ ] 10.3 After implementation, archive the change so the `ai-agent` spec absorbs
  the new requirement
