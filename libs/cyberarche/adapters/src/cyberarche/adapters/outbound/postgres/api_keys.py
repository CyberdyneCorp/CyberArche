"""ApiKeyRepository adapter over the api_keys table."""

from __future__ import annotations

import asyncpg

from cyberarche.domain.api_keys import ApiKey
from cyberarche.domain.ids import TenantId, UserId


def _from_row(row: asyncpg.Record) -> ApiKey:
    return ApiKey(
        id=row["id"],
        tenant_id=TenantId(row["tenant_id"]),
        user_id=UserId(row["user_id"]),
        name=row["name"],
        secret_hash=row["secret_hash"],
        prefix=row["prefix"],
        created_at=row["created_at"],
        expires_at=row["expires_at"],
        revoked_at=row["revoked_at"],
        last_used_at=row["last_used_at"],
    )


class PostgresApiKeyRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def add(self, key: ApiKey) -> None:
        await self._pool.execute(
            """
            INSERT INTO api_keys
                (id, tenant_id, user_id, name, secret_hash, prefix,
                 created_at, expires_at, revoked_at, last_used_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """,
            key.id,
            key.tenant_id,
            key.user_id,
            key.name,
            key.secret_hash,
            key.prefix,
            key.created_at,
            key.expires_at,
            key.revoked_at,
            key.last_used_at,
        )

    async def by_hash(self, secret_hash: str) -> ApiKey | None:
        row = await self._pool.fetchrow(
            "SELECT * FROM api_keys WHERE secret_hash = $1", secret_hash
        )
        return _from_row(row) if row else None

    async def get(self, user_id: UserId, key_id: str) -> ApiKey | None:
        row = await self._pool.fetchrow(
            "SELECT * FROM api_keys WHERE id = $1 AND user_id = $2", key_id, user_id
        )
        return _from_row(row) if row else None

    async def list_for_user(
        self, tenant_id: TenantId, user_id: UserId
    ) -> list[ApiKey]:
        rows = await self._pool.fetch(
            """
            SELECT * FROM api_keys
            WHERE tenant_id = $1 AND user_id = $2
            ORDER BY created_at
            """,
            tenant_id,
            user_id,
        )
        return [_from_row(r) for r in rows]

    async def update(self, key: ApiKey) -> None:
        await self._pool.execute(
            """
            UPDATE api_keys SET revoked_at = $2, last_used_at = $3
            WHERE id = $1
            """,
            key.id,
            key.revoked_at,
            key.last_used_at,
        )
