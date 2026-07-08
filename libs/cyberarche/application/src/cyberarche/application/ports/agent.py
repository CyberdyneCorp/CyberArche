"""Agent run auditing port (ai-agent spec)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from cyberarche.domain.ids import AgentRunId, DocumentId, TenantId, UserId


@dataclass(frozen=True, slots=True)
class AgentRun:
    id: AgentRunId
    tenant_id: TenantId
    user_id: UserId
    document_id: DocumentId | None
    model: str
    prompt: str
    tools_used: tuple[str, ...] = ()
    outcome: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class AgentRunRepository(Protocol):
    async def add(self, run: AgentRun) -> None: ...

    async def list_for_document(
        self, tenant_id: TenantId, document_id: DocumentId
    ) -> list[AgentRun]: ...
