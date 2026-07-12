"""NotificationRepository adapter over the notifications table."""

from __future__ import annotations

import asyncpg

from cyberarche.domain.ids import (
    DocumentId,
    NotificationId,
    TenantId,
    UserId,
)
from cyberarche.domain.notifications import Notification


def _from_row(row: asyncpg.Record) -> Notification:
    return Notification(
        id=NotificationId(row["id"]),
        tenant_id=TenantId(row["tenant_id"]),
        recipient_id=UserId(row["recipient_id"]),
        kind=row["kind"],
        actor_id=UserId(row["actor_id"]),
        document_id=DocumentId(row["document_id"]) if row["document_id"] else None,
        comment_id=row["comment_id"],
        snippet=row["snippet"],
        created_at=row["created_at"],
        read=row["read"],
    )


class PostgresNotificationRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def add(self, notification: Notification) -> None:
        await self._pool.execute(
            """
            INSERT INTO notifications
                (id, tenant_id, recipient_id, kind, actor_id, document_id,
                 comment_id, snippet, read, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """,
            notification.id,
            notification.tenant_id,
            notification.recipient_id,
            notification.kind,
            notification.actor_id,
            notification.document_id,
            notification.comment_id,
            notification.snippet,
            notification.read,
            notification.created_at,
        )

    async def list_for_user(
        self, tenant_id: TenantId, user_id: UserId, *, limit: int = 50
    ) -> list[Notification]:
        rows = await self._pool.fetch(
            """
            SELECT * FROM notifications
            WHERE tenant_id = $1 AND recipient_id = $2
            ORDER BY created_at DESC
            LIMIT $3
            """,
            tenant_id,
            user_id,
            limit,
        )
        return [_from_row(r) for r in rows]

    async def unread_count(self, tenant_id: TenantId, user_id: UserId) -> int:
        return await self._pool.fetchval(
            """
            SELECT COUNT(*) FROM notifications
            WHERE tenant_id = $1 AND recipient_id = $2 AND read = FALSE
            """,
            tenant_id,
            user_id,
        )

    async def mark_read(
        self, tenant_id: TenantId, user_id: UserId, notification_id: NotificationId
    ) -> None:
        await self._pool.execute(
            """
            UPDATE notifications SET read = TRUE
            WHERE id = $1 AND tenant_id = $2 AND recipient_id = $3
            """,
            notification_id,
            tenant_id,
            user_id,
        )

    async def mark_all_read(self, tenant_id: TenantId, user_id: UserId) -> None:
        await self._pool.execute(
            """
            UPDATE notifications SET read = TRUE
            WHERE tenant_id = $1 AND recipient_id = $2 AND read = FALSE
            """,
            tenant_id,
            user_id,
        )
