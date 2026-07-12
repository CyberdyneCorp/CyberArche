"""Agent persona + memory repositories over Postgres (tenant-scoped)."""

from __future__ import annotations

import asyncpg

from cyberarche.domain.agent_persona import AgentMemory, CustomInstructions
from cyberarche.domain.ids import (
    AgentMemoryId,
    CustomInstructionsId,
    TenantId,
    UserId,
    WorkspaceId,
)


def _tokens(query: str) -> list[str]:
    """Distinct lower-case keyword tokens (>=3 chars) used for recall matching."""
    seen: dict[str, None] = {}
    for raw in query.lower().split():
        token = "".join(ch for ch in raw if ch.isalnum())
        if len(token) >= 3:
            seen.setdefault(token, None)
    return list(seen)


def _instructions(row: asyncpg.Record) -> CustomInstructions:
    return CustomInstructions(
        id=CustomInstructionsId(row["id"]),
        tenant_id=TenantId(row["tenant_id"]),
        workspace_id=WorkspaceId(row["workspace_id"]),
        user_id=UserId(row["user_id"]) if row["user_id"] else None,
        instructions=row["instructions"],
        updated_by=UserId(row["updated_by"]),
        updated_at=row["updated_at"],
    )


def _memory(row: asyncpg.Record) -> AgentMemory:
    return AgentMemory(
        id=AgentMemoryId(row["id"]),
        tenant_id=TenantId(row["tenant_id"]),
        workspace_id=WorkspaceId(row["workspace_id"]),
        text=row["text"],
        created_by=UserId(row["created_by"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class PostgresCustomInstructionsRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get(
        self,
        tenant_id: TenantId,
        workspace_id: WorkspaceId,
        user_id: UserId | None,
    ) -> CustomInstructions | None:
        row = await self._pool.fetchrow(
            """
            SELECT * FROM agent_custom_instructions
            WHERE tenant_id = $1 AND workspace_id = $2
              AND user_id IS NOT DISTINCT FROM $3
            """,
            tenant_id,
            workspace_id,
            user_id,
        )
        return _instructions(row) if row else None

    async def upsert(self, record: CustomInstructions) -> None:
        await self._pool.execute(
            """
            INSERT INTO agent_custom_instructions
                (id, tenant_id, workspace_id, user_id, instructions,
                 updated_by, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (tenant_id, workspace_id, user_id)
            DO UPDATE SET instructions = EXCLUDED.instructions,
                          updated_by = EXCLUDED.updated_by,
                          updated_at = EXCLUDED.updated_at
            """,
            record.id,
            record.tenant_id,
            record.workspace_id,
            record.user_id,
            record.instructions,
            record.updated_by,
            record.updated_at,
        )

    async def clear(
        self,
        tenant_id: TenantId,
        workspace_id: WorkspaceId,
        user_id: UserId | None,
    ) -> None:
        await self._pool.execute(
            """
            DELETE FROM agent_custom_instructions
            WHERE tenant_id = $1 AND workspace_id = $2
              AND user_id IS NOT DISTINCT FROM $3
            """,
            tenant_id,
            workspace_id,
            user_id,
        )


class PostgresAgentMemoryRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def add(self, memory: AgentMemory) -> None:
        await self._pool.execute(
            """
            INSERT INTO agent_memories
                (id, tenant_id, workspace_id, text, created_by,
                 created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            memory.id,
            memory.tenant_id,
            memory.workspace_id,
            memory.text,
            memory.created_by,
            memory.created_at,
            memory.updated_at,
        )

    async def list_for_workspace(
        self, tenant_id: TenantId, workspace_id: WorkspaceId
    ) -> list[AgentMemory]:
        rows = await self._pool.fetch(
            """
            SELECT * FROM agent_memories
            WHERE tenant_id = $1 AND workspace_id = $2
            ORDER BY created_at DESC
            """,
            tenant_id,
            workspace_id,
        )
        return [_memory(r) for r in rows]

    async def recent(
        self, tenant_id: TenantId, workspace_id: WorkspaceId, limit: int
    ) -> list[AgentMemory]:
        rows = await self._pool.fetch(
            """
            SELECT * FROM agent_memories
            WHERE tenant_id = $1 AND workspace_id = $2
            ORDER BY created_at DESC
            LIMIT $3
            """,
            tenant_id,
            workspace_id,
            max(0, limit),
        )
        return [_memory(r) for r in rows]

    async def relevant(
        self,
        tenant_id: TenantId,
        workspace_id: WorkspaceId,
        query: str,
        limit: int,
    ) -> list[AgentMemory]:
        tokens = _tokens(query)
        if not tokens:
            return []
        clause = " OR ".join(f"text ILIKE ${i + 4}" for i in range(len(tokens)))
        rows = await self._pool.fetch(
            f"""
            SELECT * FROM agent_memories
            WHERE tenant_id = $1 AND workspace_id = $2 AND ({clause})
            ORDER BY created_at DESC
            LIMIT $3
            """,
            tenant_id,
            workspace_id,
            max(0, limit),
            *(f"%{token}%" for token in tokens),
        )
        return [_memory(r) for r in rows]

    async def get(
        self, tenant_id: TenantId, memory_id: AgentMemoryId
    ) -> AgentMemory | None:
        row = await self._pool.fetchrow(
            "SELECT * FROM agent_memories WHERE tenant_id = $1 AND id = $2",
            tenant_id,
            memory_id,
        )
        return _memory(row) if row else None

    async def update(self, memory: AgentMemory) -> None:
        await self._pool.execute(
            """
            UPDATE agent_memories
            SET text = $3, updated_at = $4
            WHERE tenant_id = $1 AND id = $2
            """,
            memory.tenant_id,
            memory.id,
            memory.text,
            memory.updated_at,
        )

    async def delete(
        self, tenant_id: TenantId, memory_id: AgentMemoryId
    ) -> None:
        await self._pool.execute(
            "DELETE FROM agent_memories WHERE tenant_id = $1 AND id = $2",
            tenant_id,
            memory_id,
        )
