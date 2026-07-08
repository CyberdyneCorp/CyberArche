"""RAG ports (rag-knowledge spec): CyberdyneRAG behind a provider seam."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from cyberarche.domain.ids import WorkspaceId


class RagQueryMode(StrEnum):
    LOCAL = "local"
    GLOBAL = "global"
    HYBRID = "hybrid"
    NAIVE = "naive"
    MIX = "mix"


class RagTaskStatus(StrEnum):
    PENDING = "pending"
    CONVERTING = "converting"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class RagTask:
    task_id: str
    status: RagTaskStatus
    error: str | None = None


class RagPort(Protocol):
    """Driven port over the CyberdyneRAG API (per-project isolation)."""

    async def ensure_project(self, slug: str, *, name: str) -> None: ...

    async def upload(
        self, slug: str, *, filename: str, content: bytes, content_type: str
    ) -> RagTask: ...

    async def task_status(self, slug: str, task_id: str) -> RagTask: ...

    async def query(self, slug: str, *, query: str, mode: RagQueryMode) -> str: ...

    async def delete_datasource(self, slug: str, filename: str) -> None: ...


@dataclass(frozen=True, slots=True)
class IngestionRecord:
    """Our side of an ingestion: maps a RAG task to a workspace source."""

    task_id: str
    workspace_id: WorkspaceId
    filename: str
    content_hash: str
    status: RagTaskStatus
    created_at: datetime
    error: str | None = None


class IngestionRepository(Protocol):
    async def add(self, record: IngestionRecord) -> None: ...

    async def get(
        self, workspace_id: WorkspaceId, task_id: str
    ) -> IngestionRecord | None: ...

    async def by_hash(
        self, workspace_id: WorkspaceId, content_hash: str
    ) -> IngestionRecord | None: ...

    async def by_task_id(self, task_id: str) -> IngestionRecord | None: ...

    async def list_for_workspace(
        self, workspace_id: WorkspaceId
    ) -> list[IngestionRecord]: ...

    async def update(self, record: IngestionRecord) -> None: ...

    async def delete_by_filename(
        self, workspace_id: WorkspaceId, filename: str
    ) -> None: ...
