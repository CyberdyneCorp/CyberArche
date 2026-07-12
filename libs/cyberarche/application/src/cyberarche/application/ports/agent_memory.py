"""Agent persona + memory repository ports (ai-agent spec).

Custom instructions and durable memories are tenant-isolated workspace data;
every method is filtered by `tenant_id`. The memory repo's `relevant()` is a
keyword selector in v1, shaped so a RAG-backed semantic recall can replace it
without changing the use case's call site.
"""

from __future__ import annotations

from typing import Protocol

from cyberarche.domain.agent_persona import AgentMemory, CustomInstructions
from cyberarche.domain.ids import (
    AgentMemoryId,
    TenantId,
    UserId,
    WorkspaceId,
)


class CustomInstructionsRepository(Protocol):
    async def get(
        self,
        tenant_id: TenantId,
        workspace_id: WorkspaceId,
        user_id: UserId | None,
    ) -> CustomInstructions | None:
        """The instructions row for a layer (user_id None = workspace layer)."""
        ...

    async def upsert(self, record: CustomInstructions) -> None:
        """Insert or replace the row for (tenant, workspace, user_id)."""
        ...

    async def clear(
        self,
        tenant_id: TenantId,
        workspace_id: WorkspaceId,
        user_id: UserId | None,
    ) -> None: ...


class AgentMemoryRepository(Protocol):
    async def add(self, memory: AgentMemory) -> None: ...

    async def list_for_workspace(
        self, tenant_id: TenantId, workspace_id: WorkspaceId
    ) -> list[AgentMemory]:
        """All memories for the workspace, newest first."""
        ...

    async def recent(
        self, tenant_id: TenantId, workspace_id: WorkspaceId, limit: int
    ) -> list[AgentMemory]:
        """The `limit` most recently created memories, newest first."""
        ...

    async def relevant(
        self,
        tenant_id: TenantId,
        workspace_id: WorkspaceId,
        query: str,
        limit: int,
    ) -> list[AgentMemory]:
        """Memories most relevant to `query` (v1: keyword/token overlap)."""
        ...

    async def get(
        self, tenant_id: TenantId, memory_id: AgentMemoryId
    ) -> AgentMemory | None: ...

    async def update(self, memory: AgentMemory) -> None: ...

    async def delete(self, tenant_id: TenantId, memory_id: AgentMemoryId) -> None: ...
