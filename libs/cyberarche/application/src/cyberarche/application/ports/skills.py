"""Agent skill repository port (ai-agent spec). Tenant-scoped like templates."""

from __future__ import annotations

from typing import Protocol

from cyberarche.domain.ids import AgentSkillId, TenantId, WorkspaceId
from cyberarche.domain.skills import AgentSkill


class AgentSkillRepository(Protocol):
    async def add(self, skill: AgentSkill) -> None: ...

    async def list_for_workspace(
        self, tenant_id: TenantId, workspace_id: WorkspaceId
    ) -> list[AgentSkill]:
        """The workspace's skills, newest first."""
        ...

    async def get(
        self, tenant_id: TenantId, skill_id: AgentSkillId
    ) -> AgentSkill | None: ...

    async def update(self, skill: AgentSkill) -> None: ...

    async def delete(self, tenant_id: TenantId, skill_id: AgentSkillId) -> None: ...
