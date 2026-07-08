"""UpdateLogPort adapter over the crdt_updates table."""

from __future__ import annotations

import asyncpg

from cyberarche.application.ports.crdt import LoggedUpdate
from cyberarche.domain.ids import DocumentId


def _from_row(row: asyncpg.Record) -> LoggedUpdate:
    return LoggedUpdate(
        seq=row["id"],
        document_id=DocumentId(row["document_id"]),
        update=bytes(row["update"]),
        origin=row["origin"],
        created_at=row["created_at"],
    )


class PostgresUpdateLog:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def append(
        self, document_id: DocumentId, update: bytes, *, origin: str | None
    ) -> LoggedUpdate:
        row = await self._pool.fetchrow(
            """
            INSERT INTO crdt_updates (document_id, update, origin)
            VALUES ($1, $2, $3)
            RETURNING *
            """,
            document_id,
            update,
            origin,
        )
        return _from_row(row)

    async def list_for_document(self, document_id: DocumentId) -> list[LoggedUpdate]:
        rows = await self._pool.fetch(
            "SELECT * FROM crdt_updates WHERE document_id = $1 ORDER BY id",
            document_id,
        )
        return [_from_row(r) for r in rows]

    async def count(self, document_id: DocumentId) -> int:
        return await self._pool.fetchval(
            "SELECT count(*) FROM crdt_updates WHERE document_id = $1", document_id
        )

    async def replace_with(
        self, document_id: DocumentId, merged: bytes, *, up_to_seq: int
    ) -> None:
        async with self._pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    "DELETE FROM crdt_updates WHERE document_id = $1 AND id <= $2",
                    document_id,
                    up_to_seq,
                )
                await connection.execute(
                    """
                    INSERT INTO crdt_updates (document_id, update, origin)
                    VALUES ($1, $2, 'compaction')
                    """,
                    document_id,
                    merged,
                )
