"""PostgresUpdateLog adapter: SQL parameter mapping and row decoding.

Unit-level: a scripted pool/connection stands in for asyncpg so append,
listing, counting, and transactional compaction are covered without a
database. The cross-backend behavior itself lives in test_port_contracts.
"""

from __future__ import annotations

from datetime import UTC, datetime

from cyberarche.adapters.outbound.postgres.update_log import PostgresUpdateLog
from cyberarche.domain.ids import DocumentId

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _row(seq: int = 1, update: object = b"u1", origin: str | None = "alice") -> dict:
    return {
        "id": seq,
        "document_id": "d-1",
        "update": update,
        "origin": origin,
        "created_at": NOW,
    }


class _ScriptedTransaction:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    async def __aenter__(self) -> "_ScriptedTransaction":
        self._events.append("begin")
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        self._events.append("commit" if exc_type is None else "rollback")
        return False


class _ScriptedConnection:
    def __init__(self) -> None:
        self.events: list[str] = []
        self.calls: list[tuple[str, tuple]] = []

    def transaction(self) -> _ScriptedTransaction:
        return _ScriptedTransaction(self.events)

    async def execute(self, query: str, *args) -> str:
        self.calls.append((query, args))
        return "OK"


class _Acquired:
    def __init__(self, connection: _ScriptedConnection) -> None:
        self._connection = connection

    async def __aenter__(self) -> _ScriptedConnection:
        return self._connection

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class _ScriptedPool:
    """Records queries and replays canned rows (dicts stand in for Records)."""

    def __init__(
        self,
        *,
        rows: list[dict] | None = None,
        row: dict | None = None,
        value: int | None = None,
    ) -> None:
        self.calls: list[tuple[str, str, tuple]] = []
        self.connection = _ScriptedConnection()
        self._rows = rows or []
        self._row = row
        self._value = value

    async def fetch(self, query: str, *args) -> list[dict]:
        self.calls.append(("fetch", query, args))
        return self._rows

    async def fetchrow(self, query: str, *args) -> dict | None:
        self.calls.append(("fetchrow", query, args))
        return self._row

    async def fetchval(self, query: str, *args) -> int | None:
        self.calls.append(("fetchval", query, args))
        return self._value

    def acquire(self) -> _Acquired:
        return _Acquired(self.connection)


async def test_append_inserts_and_returns_the_logged_update():
    # asyncpg hands bytea back as non-bytes buffers too; bytes() must normalize.
    pool = _ScriptedPool(row=_row(seq=7, update=memoryview(b"u1")))
    logged = await PostgresUpdateLog(pool).append(
        DocumentId("d-1"), b"u1", origin="alice"
    )

    assert logged.seq == 7
    assert logged.document_id == "d-1"
    assert logged.update == b"u1" and isinstance(logged.update, bytes)
    assert logged.origin == "alice"
    assert logged.created_at == NOW
    kind, query, args = pool.calls[0]
    assert kind == "fetchrow" and "RETURNING *" in query
    assert args == ("d-1", b"u1", "alice")


async def test_append_preserves_a_none_origin():
    pool = _ScriptedPool(row=_row(origin=None))
    logged = await PostgresUpdateLog(pool).append(DocumentId("d-1"), b"u1", origin=None)

    assert logged.origin is None
    assert pool.calls[0][2] == ("d-1", b"u1", None)


async def test_list_for_document_maps_rows_in_sequence_order():
    pool = _ScriptedPool(rows=[_row(seq=1, update=b"u1"), _row(seq=2, update=b"u2")])
    listed = await PostgresUpdateLog(pool).list_for_document(DocumentId("d-1"))

    assert [(u.seq, u.update) for u in listed] == [(1, b"u1"), (2, b"u2")]
    kind, query, args = pool.calls[0]
    assert kind == "fetch" and "ORDER BY id" in query and args == ("d-1",)


async def test_list_for_document_empty_log():
    pool = _ScriptedPool(rows=[])
    assert await PostgresUpdateLog(pool).list_for_document(DocumentId("d-1")) == []


async def test_count_scopes_to_the_document():
    pool = _ScriptedPool(value=3)
    assert await PostgresUpdateLog(pool).count(DocumentId("d-1")) == 3
    kind, query, args = pool.calls[0]
    assert kind == "fetchval" and "count(*)" in query and args == ("d-1",)


async def test_replace_with_deletes_then_inserts_inside_one_transaction():
    pool = _ScriptedPool()
    await PostgresUpdateLog(pool).replace_with(
        DocumentId("d-1"), b"merged", up_to_seq=42
    )

    connection = pool.connection
    assert connection.events == ["begin", "commit"]  # both statements share a tx

    (delete_query, delete_args), (insert_query, insert_args) = connection.calls
    assert "DELETE FROM crdt_updates" in delete_query and "id <= $2" in delete_query
    assert delete_args == ("d-1", 42)
    assert "INSERT INTO crdt_updates" in insert_query and "'compaction'" in insert_query
    assert insert_args == ("d-1", b"merged")
