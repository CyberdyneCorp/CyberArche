"""GoogleConnectionRepository over Postgres. Tokens are stored as encrypted
BYTEA and never returned in plaintext; only metadata is read back via `get`."""

from __future__ import annotations

import json
from datetime import datetime

import asyncpg

from cyberarche.domain.google_workspace import GoogleConnection
from cyberarche.domain.ids import (
    GoogleConnectionId,
    TenantId,
    UserId,
    WorkspaceId,
)


def _metadata(row: asyncpg.Record) -> GoogleConnection:
    scopes = row["scopes"]
    if isinstance(scopes, str):
        scopes = json.loads(scopes)
    return GoogleConnection(
        id=GoogleConnectionId(row["id"]),
        tenant_id=TenantId(row["tenant_id"]),
        workspace_id=WorkspaceId(row["workspace_id"]),
        user_id=UserId(row["user_id"]),
        google_email=row["google_email"],
        status=row["status"],
        scopes=list(scopes or []),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        token_expires_at=row["token_expires_at"],
    )


class PostgresGoogleConnectionRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def upsert(
        self,
        connection: GoogleConnection,
        *,
        access_encrypted: bytes,
        refresh_encrypted: bytes,
    ) -> None:
        await self._pool.execute(
            """
            INSERT INTO google_connections
                (id, tenant_id, workspace_id, user_id, google_email,
                 access_token_encrypted, refresh_token_encrypted,
                 token_expires_at, scopes, status, created_at, updated_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb,$10,$11,$12)
            ON CONFLICT (tenant_id, workspace_id, user_id) DO UPDATE SET
                google_email = EXCLUDED.google_email,
                access_token_encrypted = EXCLUDED.access_token_encrypted,
                refresh_token_encrypted = EXCLUDED.refresh_token_encrypted,
                token_expires_at = EXCLUDED.token_expires_at,
                scopes = EXCLUDED.scopes,
                status = EXCLUDED.status,
                updated_at = EXCLUDED.updated_at
            """,
            connection.id, connection.tenant_id, connection.workspace_id,
            connection.user_id, connection.google_email, access_encrypted,
            refresh_encrypted, connection.token_expires_at,
            json.dumps(connection.scopes), connection.status,
            connection.created_at, connection.updated_at,
        )

    async def get(
        self, tenant_id: TenantId, workspace_id: WorkspaceId, user_id: UserId
    ) -> GoogleConnection | None:
        row = await self._pool.fetchrow(
            """
            SELECT * FROM google_connections
            WHERE tenant_id = $1 AND workspace_id = $2 AND user_id = $3
            """,
            tenant_id,
            workspace_id,
            user_id,
        )
        return _metadata(row) if row else None

    async def read_secrets(
        self, tenant_id: TenantId, workspace_id: WorkspaceId, user_id: UserId
    ) -> tuple[bytes, bytes] | None:
        row = await self._pool.fetchrow(
            """
            SELECT access_token_encrypted, refresh_token_encrypted
            FROM google_connections
            WHERE tenant_id = $1 AND workspace_id = $2 AND user_id = $3
            """,
            tenant_id,
            workspace_id,
            user_id,
        )
        if row is None:
            return None
        return bytes(row["access_token_encrypted"]), bytes(
            row["refresh_token_encrypted"]
        )

    async def set_status(
        self,
        tenant_id: TenantId,
        workspace_id: WorkspaceId,
        user_id: UserId,
        status: str,
        updated_at: datetime,
    ) -> None:
        await self._pool.execute(
            """
            UPDATE google_connections SET status = $4, updated_at = $5
            WHERE tenant_id = $1 AND workspace_id = $2 AND user_id = $3
            """,
            tenant_id,
            workspace_id,
            user_id,
            status,
            updated_at,
        )

    async def delete(
        self, tenant_id: TenantId, workspace_id: WorkspaceId, user_id: UserId
    ) -> None:
        await self._pool.execute(
            """
            DELETE FROM google_connections
            WHERE tenant_id = $1 AND workspace_id = $2 AND user_id = $3
            """,
            tenant_id,
            workspace_id,
            user_id,
        )
