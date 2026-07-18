"""NotificationPreferencesRepository adapter over the notification_preferences
table (one row per tenant+user; absent row => defaults)."""

from __future__ import annotations

from datetime import datetime

import asyncpg

from cyberarche.domain.ids import TenantId, UserId
from cyberarche.domain.notifications import NotificationPreferences


def _from_row(row: asyncpg.Record) -> NotificationPreferences:
    return NotificationPreferences(
        tenant_id=TenantId(row["tenant_id"]),
        user_id=UserId(row["user_id"]),
        email_enabled=row["email_enabled"],
        push_enabled=row["push_enabled"],
        mentions_enabled=row["mentions_enabled"],
        agent_results_enabled=row["agent_results_enabled"],
        email=row["email"],
        last_digest_at=row["last_digest_at"],
    )


class PostgresNotificationPreferencesRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get(
        self, tenant_id: TenantId, user_id: UserId
    ) -> NotificationPreferences | None:
        row = await self._pool.fetchrow(
            """
            SELECT * FROM notification_preferences
            WHERE tenant_id = $1 AND user_id = $2
            """,
            tenant_id,
            user_id,
        )
        return _from_row(row) if row else None

    async def upsert(self, prefs: NotificationPreferences) -> None:
        await self._pool.execute(
            """
            INSERT INTO notification_preferences
                (tenant_id, user_id, email_enabled, push_enabled,
                 mentions_enabled, agent_results_enabled, email, last_digest_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (tenant_id, user_id) DO UPDATE SET
                email_enabled = EXCLUDED.email_enabled,
                push_enabled = EXCLUDED.push_enabled,
                mentions_enabled = EXCLUDED.mentions_enabled,
                agent_results_enabled = EXCLUDED.agent_results_enabled,
                email = EXCLUDED.email,
                last_digest_at = EXCLUDED.last_digest_at
            """,
            prefs.tenant_id,
            prefs.user_id,
            prefs.email_enabled,
            prefs.push_enabled,
            prefs.mentions_enabled,
            prefs.agent_results_enabled,
            prefs.email,
            prefs.last_digest_at,
        )

    async def list_email_recipients(self) -> list[NotificationPreferences]:
        rows = await self._pool.fetch(
            """
            SELECT * FROM notification_preferences
            WHERE email_enabled = TRUE AND email IS NOT NULL AND email <> ''
            """
        )
        return [_from_row(r) for r in rows]

    async def mark_digested(
        self, tenant_id: TenantId, user_id: UserId, at: datetime
    ) -> None:
        await self._pool.execute(
            """
            UPDATE notification_preferences SET last_digest_at = $3
            WHERE tenant_id = $1 AND user_id = $2
            """,
            tenant_id,
            user_id,
            at,
        )
