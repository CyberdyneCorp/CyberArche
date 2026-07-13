"""PostgresIngestionRepository wire-level behavior over a recording fake pool."""

from __future__ import annotations

from datetime import UTC, datetime

from cyberarche.adapters.outbound.postgres.ingestions import (
    PostgresIngestionRepository,
)
from cyberarche.application.ports.rag import IngestionRecord, RagTaskStatus
from cyberarche.domain.ids import WorkspaceId

NOW = datetime(2026, 1, 1, tzinfo=UTC)


class FakePool:
    """Records (query, args) calls; returns canned rows for fetch/fetchrow."""

    def __init__(self, rows: list[dict] | None = None) -> None:
        self.rows = rows or []
        self.calls: list[tuple[str, tuple]] = []

    async def fetch(self, query: str, *args) -> list[dict]:
        self.calls.append((query, args))
        return self.rows

    async def fetchrow(self, query: str, *args) -> dict | None:
        self.calls.append((query, args))
        return self.rows[0] if self.rows else None

    async def execute(self, query: str, *args) -> str:
        self.calls.append((query, args))
        return "INSERT 0 1"


def record(**kw) -> IngestionRecord:
    return IngestionRecord(
        task_id=kw.get("task_id", "task-1"),
        workspace_id=WorkspaceId(kw.get("workspace_id", "ws-1")),
        filename=kw.get("filename", "notes.pdf"),
        content_hash=kw.get("content_hash", "hash-1"),
        status=kw.get("status", RagTaskStatus.PENDING),
        created_at=kw.get("created_at", NOW),
        error=kw.get("error"),
    )


def row(**kw) -> dict:
    return {
        "task_id": kw.get("task_id", "task-1"),
        "workspace_id": kw.get("workspace_id", "ws-1"),
        "filename": kw.get("filename", "notes.pdf"),
        "content_hash": kw.get("content_hash", "hash-1"),
        "status": kw.get("status", "completed"),
        "created_at": kw.get("created_at", NOW),
        "error": kw.get("error"),
    }


async def test_add_inserts_all_columns_with_status_value():
    pool = FakePool()
    repo = PostgresIngestionRepository(pool)

    await repo.add(record(status=RagTaskStatus.PROCESSING, error="oops"))

    query, args = pool.calls[0]
    assert "INSERT INTO ingestion_tasks" in query
    assert args == ("task-1", "ws-1", "notes.pdf", "hash-1", "processing", "oops", NOW)


async def test_get_maps_row_to_record():
    pool = FakePool(rows=[row(status="failed", error="boom")])
    repo = PostgresIngestionRepository(pool)

    got = await repo.get(WorkspaceId("ws-1"), "task-1")

    assert got == record(status=RagTaskStatus.FAILED, error="boom")
    assert isinstance(got.status, RagTaskStatus)
    query, args = pool.calls[0]
    assert "WHERE task_id = $1 AND workspace_id = $2" in query
    assert args == ("task-1", "ws-1")  # scoped to the workspace


async def test_get_returns_none_when_missing():
    repo = PostgresIngestionRepository(FakePool())
    assert await repo.get(WorkspaceId("ws-1"), "task-404") is None


async def test_by_hash_returns_latest_record_for_hash():
    pool = FakePool(rows=[row()])
    repo = PostgresIngestionRepository(pool)

    got = await repo.by_hash(WorkspaceId("ws-1"), "hash-1")

    assert got == record(status=RagTaskStatus.COMPLETED)
    query, args = pool.calls[0]
    assert "ORDER BY created_at DESC LIMIT 1" in query
    assert args == ("ws-1", "hash-1")


async def test_by_hash_returns_none_when_missing():
    repo = PostgresIngestionRepository(FakePool())
    assert await repo.by_hash(WorkspaceId("ws-1"), "hash-404") is None


async def test_by_task_id_looks_up_across_workspaces():
    pool = FakePool(rows=[row(status="converting")])
    repo = PostgresIngestionRepository(pool)

    got = await repo.by_task_id("task-1")

    assert got == record(status=RagTaskStatus.CONVERTING)
    query, args = pool.calls[0]
    assert "workspace_id" not in query.split("WHERE")[1]  # unscoped lookup
    assert args == ("task-1",)


async def test_by_task_id_returns_none_when_missing():
    repo = PostgresIngestionRepository(FakePool())
    assert await repo.by_task_id("task-404") is None


async def test_list_for_workspace_maps_every_row():
    pool = FakePool(
        rows=[row(task_id="task-1"), row(task_id="task-2", status="pending")]
    )
    repo = PostgresIngestionRepository(pool)

    got = await repo.list_for_workspace(WorkspaceId("ws-1"))

    assert [r.task_id for r in got] == ["task-1", "task-2"]
    assert got[1].status is RagTaskStatus.PENDING
    query, args = pool.calls[0]
    assert "ORDER BY created_at" in query
    assert args == ("ws-1",)


async def test_list_for_workspace_returns_empty_list():
    repo = PostgresIngestionRepository(FakePool())
    assert await repo.list_for_workspace(WorkspaceId("ws-empty")) == []


async def test_update_writes_status_and_error_by_task_id():
    pool = FakePool()
    repo = PostgresIngestionRepository(pool)

    await repo.update(record(status=RagTaskStatus.FAILED, error="parse error"))

    query, args = pool.calls[0]
    assert query.startswith("UPDATE ingestion_tasks")
    assert args == ("task-1", "failed", "parse error")


async def test_delete_by_filename_scopes_to_workspace():
    pool = FakePool()
    repo = PostgresIngestionRepository(pool)

    await repo.delete_by_filename(WorkspaceId("ws-1"), "notes.pdf")

    query, args = pool.calls[0]
    assert query.startswith("DELETE FROM ingestion_tasks")
    assert args == ("ws-1", "notes.pdf")
