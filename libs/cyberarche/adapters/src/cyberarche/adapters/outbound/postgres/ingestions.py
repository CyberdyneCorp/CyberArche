"""IngestionRepository adapter over the ingestion_tasks table."""

from __future__ import annotations

import asyncpg

from cyberarche.application.ports.rag import IngestionRecord, RagTaskStatus
from cyberarche.domain.ids import WorkspaceId


def _from_row(row: asyncpg.Record) -> IngestionRecord:
    return IngestionRecord(
        task_id=row["task_id"],
        workspace_id=WorkspaceId(row["workspace_id"]),
        filename=row["filename"],
        content_hash=row["content_hash"],
        status=RagTaskStatus(row["status"]),
        created_at=row["created_at"],
        error=row["error"],
    )


class PostgresIngestionRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def add(self, record: IngestionRecord) -> None:
        await self._pool.execute(
            """
            INSERT INTO ingestion_tasks
                (task_id, workspace_id, filename, content_hash, status, error, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            record.task_id,
            record.workspace_id,
            record.filename,
            record.content_hash,
            record.status.value,
            record.error,
            record.created_at,
        )

    async def get(
        self, workspace_id: WorkspaceId, task_id: str
    ) -> IngestionRecord | None:
        row = await self._pool.fetchrow(
            "SELECT * FROM ingestion_tasks WHERE task_id = $1 AND workspace_id = $2",
            task_id,
            workspace_id,
        )
        return _from_row(row) if row else None

    async def by_hash(
        self, workspace_id: WorkspaceId, content_hash: str
    ) -> IngestionRecord | None:
        row = await self._pool.fetchrow(
            """
            SELECT * FROM ingestion_tasks
            WHERE workspace_id = $1 AND content_hash = $2
            ORDER BY created_at DESC LIMIT 1
            """,
            workspace_id,
            content_hash,
        )
        return _from_row(row) if row else None

    async def by_task_id(self, task_id: str) -> IngestionRecord | None:
        row = await self._pool.fetchrow(
            "SELECT * FROM ingestion_tasks WHERE task_id = $1", task_id
        )
        return _from_row(row) if row else None

    async def list_for_workspace(
        self, workspace_id: WorkspaceId
    ) -> list[IngestionRecord]:
        rows = await self._pool.fetch(
            "SELECT * FROM ingestion_tasks WHERE workspace_id = $1 ORDER BY created_at",
            workspace_id,
        )
        return [_from_row(r) for r in rows]

    async def update(self, record: IngestionRecord) -> None:
        await self._pool.execute(
            "UPDATE ingestion_tasks SET status = $2, error = $3 WHERE task_id = $1",
            record.task_id,
            record.status.value,
            record.error,
        )

    async def delete_by_filename(
        self, workspace_id: WorkspaceId, filename: str
    ) -> None:
        await self._pool.execute(
            "DELETE FROM ingestion_tasks WHERE workspace_id = $1 AND filename = $2",
            workspace_id,
            filename,
        )
