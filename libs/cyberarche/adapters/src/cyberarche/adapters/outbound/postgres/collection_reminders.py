"""ReminderStateRepository adapter over the collection_reminders table.

One row per (document_id, property_id) holds the last date value a reminder
fired for. A reminder is considered already sent iff the stored value equals the
given value, so changing a row's date value re-arms the reminder.
"""

from __future__ import annotations

import asyncpg


class PostgresReminderStateRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def was_reminded(
        self, document_id: str, property_id: str, value: str
    ) -> bool:
        stored = await self._pool.fetchval(
            """
            SELECT reminded_value FROM collection_reminders
            WHERE document_id = $1 AND property_id = $2
            """,
            document_id,
            property_id,
        )
        return stored == value

    async def mark_reminded(
        self, document_id: str, property_id: str, value: str
    ) -> None:
        await self._pool.execute(
            """
            INSERT INTO collection_reminders (document_id, property_id, reminded_value)
            VALUES ($1, $2, $3)
            ON CONFLICT (document_id, property_id) DO UPDATE SET
                reminded_value = EXCLUDED.reminded_value
            """,
            document_id,
            property_id,
            value,
        )
