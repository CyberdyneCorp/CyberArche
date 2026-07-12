"""Agent skill use cases (ai-agent spec): save/list/update/delete named agent
instructions and expand one into a concrete instruction string.

A skill is a saved, parameterized producer of the `instruction` argument the
agent's `ask()` already accepts — there is no new agent-loop mechanic here.
Permissions mirror templates: VIEWER to list/run, EDITOR to create/edit,
creator-or-OWNER to delete.
"""

from __future__ import annotations

from cyberarche.application.authz import AccessControl
from cyberarche.application.kernel import CallerContext
from cyberarche.application.ports.skills import AgentSkillRepository
from cyberarche.application.ports.telemetry import ClockPort, IdPort
from cyberarche.domain.errors import NotAuthorized, NotFound, ValidationFailed
from cyberarche.domain.ids import AgentSkillId, WorkspaceId
from cyberarche.domain.memberships import Role
from cyberarche.domain.skills import AgentSkill, expand, parse_variables


class AgentSkillUseCases:
    def __init__(
        self,
        skills: AgentSkillRepository,
        access: AccessControl,
        clock: ClockPort,
        ids: IdPort,
    ) -> None:
        self._skills = skills
        self._access = access
        self._clock = clock
        self._ids = ids

    async def list(
        self, caller: CallerContext, workspace_id: WorkspaceId
    ) -> list[AgentSkill]:
        await self._access.require_workspace(caller, workspace_id, Role.VIEWER)
        return await self._skills.list_for_workspace(caller.tenant_id, workspace_id)

    async def save(
        self,
        caller: CallerContext,
        workspace_id: WorkspaceId,
        *,
        name: str,
        instruction: str,
        description: str = "",
    ) -> AgentSkill:
        await self._access.require_workspace(caller, workspace_id, Role.EDITOR)
        name = name.strip()
        instruction = instruction.strip()
        if not name or not instruction:
            raise ValidationFailed("skill name and instruction are required")
        skill = AgentSkill(
            id=AgentSkillId(self._ids.new_id()),
            tenant_id=caller.tenant_id,
            workspace_id=workspace_id,
            name=name,
            description=description.strip(),
            instruction=instruction,
            variables=parse_variables(instruction),
            created_by=caller.user_id,
            created_at=self._clock.now(),
        )
        await self._skills.add(skill)
        return skill

    async def update(
        self,
        caller: CallerContext,
        workspace_id: WorkspaceId,
        skill_id: AgentSkillId,
        *,
        name: str,
        instruction: str,
        description: str = "",
    ) -> AgentSkill:
        await self._access.require_workspace(caller, workspace_id, Role.EDITOR)
        existing = await self._require_skill(caller, workspace_id, skill_id)
        name = name.strip()
        instruction = instruction.strip()
        if not name or not instruction:
            raise ValidationFailed("skill name and instruction are required")
        updated = AgentSkill(
            id=existing.id,
            tenant_id=existing.tenant_id,
            workspace_id=existing.workspace_id,
            name=name,
            description=description.strip(),
            instruction=instruction,
            variables=parse_variables(instruction),
            created_by=existing.created_by,
            created_at=existing.created_at,
        )
        await self._skills.update(updated)
        return updated

    async def delete(
        self,
        caller: CallerContext,
        workspace_id: WorkspaceId,
        skill_id: AgentSkillId,
    ) -> None:
        skill = await self._require_skill(caller, workspace_id, skill_id)
        role = await self._access.workspace_role(caller, workspace_id)
        is_owner = role == Role.OWNER
        if not is_owner and str(skill.created_by) != str(caller.user_id):
            raise NotAuthorized("only the creator or a workspace owner may delete")
        await self._skills.delete(caller.tenant_id, skill_id)

    async def instantiate(
        self,
        caller: CallerContext,
        workspace_id: WorkspaceId,
        skill_id: AgentSkillId,
        values: dict[str, str],
    ) -> str:
        """Expand a skill into a concrete instruction string (no LLM call)."""
        skill = await self._require_skill(caller, workspace_id, skill_id)
        return expand(skill.instruction, skill.variables, values or {})

    async def _require_skill(
        self,
        caller: CallerContext,
        workspace_id: WorkspaceId,
        skill_id: AgentSkillId,
    ) -> AgentSkill:
        await self._access.require_workspace(caller, workspace_id, Role.VIEWER)
        skill = await self._skills.get(caller.tenant_id, skill_id)
        if skill is None or str(skill.workspace_id) != str(workspace_id):
            raise NotFound("skill not found")
        return skill
