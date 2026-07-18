"""PushSubscriptionRepository adapter over the push_subscriptions table (one row
per browser endpoint; `endpoint` is the primary key across all users)."""

from __future__ import annotations

import asyncpg

from cyberarche.domain.ids import TenantId, UserId
from cyberarche.domain.push import PushSubscription


def _from_row(row: asyncpg.Record) -> PushSubscription:
    return PushSubscription(
        tenant_id=TenantId(row["tenant_id"]),
        user_id=UserId(row["user_id"]),
        endpoint=row["endpoint"],
        p256dh=row["p256dh"],
        auth=row["auth"],
        created_at=row["created_at"],
    )


class PostgresPushSubscriptionRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def add(self, sub: PushSubscription) -> None:
        await self._pool.execute(
            """
            INSERT INTO push_subscriptions
                (tenant_id, user_id, endpoint, p256dh, auth, created_at)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (endpoint) DO UPDATE SET
                tenant_id = EXCLUDED.tenant_id,
                user_id = EXCLUDED.user_id,
                p256dh = EXCLUDED.p256dh,
                auth = EXCLUDED.auth,
                created_at = EXCLUDED.created_at
            """,
            sub.tenant_id,
            sub.user_id,
            sub.endpoint,
            sub.p256dh,
            sub.auth,
            sub.created_at,
        )

    async def list_for_user(
        self, tenant_id: TenantId, user_id: UserId
    ) -> list[PushSubscription]:
        rows = await self._pool.fetch(
            """
            SELECT * FROM push_subscriptions
            WHERE tenant_id = $1 AND user_id = $2
            ORDER BY created_at
            """,
            tenant_id,
            user_id,
        )
        return [_from_row(r) for r in rows]

    async def remove(
        self, tenant_id: TenantId, user_id: UserId, endpoint: str
    ) -> None:
        await self._pool.execute(
            """
            DELETE FROM push_subscriptions
            WHERE tenant_id = $1 AND user_id = $2 AND endpoint = $3
            """,
            tenant_id,
            user_id,
            endpoint,
        )

    async def remove_by_endpoint(self, endpoint: str) -> None:
        await self._pool.execute(
            "DELETE FROM push_subscriptions WHERE endpoint = $1",
            endpoint,
        )
