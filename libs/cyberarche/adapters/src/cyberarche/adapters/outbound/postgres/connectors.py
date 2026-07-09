"""ConnectorRepository adapter over the mcp_connectors table."""

from __future__ import annotations

import asyncpg

from cyberarche.domain.connectors import Connector
from cyberarche.domain.errors import NotFound
from cyberarche.domain.ids import (
    ConnectorId,
    DocumentId,
    TenantId,
    UserId,
    WorkspaceId,
)


def _from_row(row: asyncpg.Record) -> Connector:
    return Connector(
        id=ConnectorId(row["id"]),
        tenant_id=TenantId(row["tenant_id"]),
        workspace_id=WorkspaceId(row["workspace_id"]),
        name=row["name"],
        slug=row["slug"],
        endpoint=row["endpoint"],
        enabled=row["enabled"],
        created_by=UserId(row["created_by"]),
        created_at=row["created_at"],
        document_id=DocumentId(row["document_id"]) if row["document_id"] else None,
    )


class PostgresConnectorRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def add(self, connector: Connector, credentials_encrypted: bytes) -> None:
        await self._pool.execute(
            """
            INSERT INTO mcp_connectors
                (id, tenant_id, workspace_id, name, slug, endpoint,
                 credentials_encrypted, enabled, created_by, created_at, document_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            """,
            connector.id,
            connector.tenant_id,
            connector.workspace_id,
            connector.name,
            connector.slug,
            connector.endpoint,
            credentials_encrypted,
            connector.enabled,
            connector.created_by,
            connector.created_at,
            connector.document_id,
        )

    async def get(
        self, tenant_id: TenantId, connector_id: ConnectorId
    ) -> Connector | None:
        row = await self._pool.fetchrow(
            "SELECT * FROM mcp_connectors WHERE id = $1 AND tenant_id = $2",
            connector_id,
            tenant_id,
        )
        return _from_row(row) if row else None

    async def credentials(self, connector_id: ConnectorId) -> bytes:
        value = await self._pool.fetchval(
            "SELECT credentials_encrypted FROM mcp_connectors WHERE id = $1",
            connector_id,
        )
        if value is None:
            raise NotFound("connector not found")
        return bytes(value)

    async def list_for_workspace(
        self, tenant_id: TenantId, workspace_id: WorkspaceId
    ) -> list[Connector]:
        rows = await self._pool.fetch(
            """
            SELECT * FROM mcp_connectors
            WHERE tenant_id = $1 AND workspace_id = $2
            ORDER BY created_at
            """,
            tenant_id,
            workspace_id,
        )
        return [_from_row(r) for r in rows]

    async def by_slug(
        self, tenant_id: TenantId, workspace_id: WorkspaceId, slug: str
    ) -> Connector | None:
        row = await self._pool.fetchrow(
            """
            SELECT * FROM mcp_connectors
            WHERE tenant_id = $1 AND workspace_id = $2 AND slug = $3
            """,
            tenant_id,
            workspace_id,
            slug,
        )
        return _from_row(row) if row else None

    async def update(self, connector: Connector) -> None:
        await self._pool.execute(
            "UPDATE mcp_connectors SET name = $2, enabled = $3 WHERE id = $1",
            connector.id,
            connector.name,
            connector.enabled,
        )

    async def delete(self, tenant_id: TenantId, connector_id: ConnectorId) -> None:
        await self._pool.execute(
            "DELETE FROM mcp_connectors WHERE id = $1 AND tenant_id = $2",
            connector_id,
            tenant_id,
        )
