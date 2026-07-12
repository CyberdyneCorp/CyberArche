"""AgentSkillRepository adapter over the agent_skills table."""

from __future__ import annotations

import json

import asyncpg

from cyberarche.domain.ids import AgentSkillId, TenantId, UserId, WorkspaceId
from cyberarche.domain.skills import AgentSkill


def _from_row(row: asyncpg.Record) -> AgentSkill:
    variables = row["variables"]
    if isinstance(variables, str):
        variables = json.loads(variables)
    return AgentSkill(
        id=AgentSkillId(row["id"]),
        tenant_id=TenantId(row["tenant_id"]),
        workspace_id=WorkspaceId(row["workspace_id"]),
        name=row["name"],
        description=row["description"],
        instruction=row["instruction"],
        variables=list(variables or []),
        created_by=UserId(row["created_by"]),
        created_at=row["created_at"],
    )


class PostgresAgentSkillRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def add(self, skill: AgentSkill) -> None:
        await self._pool.execute(
            """
            INSERT INTO agent_skills
                (id, tenant_id, workspace_id, name, description, instruction,
                 variables, created_by, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8, $9)
            """,
            skill.id,
            skill.tenant_id,
            skill.workspace_id,
            skill.name,
            skill.description,
            skill.instruction,
            json.dumps(skill.variables),
            skill.created_by,
            skill.created_at,
        )

    async def list_for_workspace(
        self, tenant_id: TenantId, workspace_id: WorkspaceId
    ) -> list[AgentSkill]:
        rows = await self._pool.fetch(
            """
            SELECT * FROM agent_skills
            WHERE tenant_id = $1 AND workspace_id = $2
            ORDER BY created_at DESC
            """,
            tenant_id,
            workspace_id,
        )
        return [_from_row(r) for r in rows]

    async def get(
        self, tenant_id: TenantId, skill_id: AgentSkillId
    ) -> AgentSkill | None:
        row = await self._pool.fetchrow(
            "SELECT * FROM agent_skills WHERE tenant_id = $1 AND id = $2",
            tenant_id,
            skill_id,
        )
        return _from_row(row) if row else None

    async def update(self, skill: AgentSkill) -> None:
        await self._pool.execute(
            """
            UPDATE agent_skills
            SET name = $3, description = $4, instruction = $5, variables = $6::jsonb
            WHERE tenant_id = $1 AND id = $2
            """,
            skill.tenant_id,
            skill.id,
            skill.name,
            skill.description,
            skill.instruction,
            json.dumps(skill.variables),
        )

    async def delete(self, tenant_id: TenantId, skill_id: AgentSkillId) -> None:
        await self._pool.execute(
            "DELETE FROM agent_skills WHERE tenant_id = $1 AND id = $2",
            tenant_id,
            skill_id,
        )
