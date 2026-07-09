"""Folder repository over Postgres."""

from __future__ import annotations

import asyncpg

from cyberarche.domain.folders import Folder
from cyberarche.domain.ids import (
    FolderId,
    TeamspaceId,
    TenantId,
    UserId,
    WorkspaceId,
)


def _from_row(row: asyncpg.Record) -> Folder:
    return Folder(
        id=FolderId(row["id"]),
        workspace_id=WorkspaceId(row["workspace_id"]),
        tenant_id=TenantId(row["tenant_id"]),
        name=row["name"],
        created_by=UserId(row["created_by"]),
        created_at=row["created_at"],
        teamspace_id=TeamspaceId(row["teamspace_id"]) if row["teamspace_id"] else None,
        parent_folder_id=(
            FolderId(row["parent_folder_id"]) if row["parent_folder_id"] else None
        ),
    )


class PostgresFolderRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def add(self, folder: Folder) -> None:
        await self._pool.execute(
            """
            INSERT INTO folders
                (id, workspace_id, tenant_id, name, created_by, created_at,
                 teamspace_id, parent_folder_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            folder.id,
            folder.workspace_id,
            folder.tenant_id,
            folder.name,
            folder.created_by,
            folder.created_at,
            folder.teamspace_id,
            folder.parent_folder_id,
        )

    async def get(self, tenant_id: TenantId, folder_id: FolderId) -> Folder | None:
        row = await self._pool.fetchrow(
            "SELECT * FROM folders WHERE id = $1 AND tenant_id = $2",
            folder_id,
            tenant_id,
        )
        return _from_row(row) if row else None

    async def list_for_workspace(
        self, tenant_id: TenantId, workspace_id: WorkspaceId
    ) -> list[Folder]:
        rows = await self._pool.fetch(
            "SELECT * FROM folders WHERE tenant_id = $1 AND workspace_id = $2"
            " ORDER BY name",
            tenant_id,
            workspace_id,
        )
        return [_from_row(r) for r in rows]

    async def list_for_teamspace(
        self, tenant_id: TenantId, teamspace_id: TeamspaceId
    ) -> list[Folder]:
        rows = await self._pool.fetch(
            "SELECT * FROM folders WHERE tenant_id = $1 AND teamspace_id = $2"
            " ORDER BY name",
            tenant_id,
            teamspace_id,
        )
        return [_from_row(r) for r in rows]

    async def update(self, folder: Folder) -> None:
        await self._pool.execute(
            "UPDATE folders SET name = $2 WHERE id = $1", folder.id, folder.name
        )

    async def delete(self, tenant_id: TenantId, folder_id: FolderId) -> None:
        await self._pool.execute(
            "DELETE FROM folders WHERE id = $1 AND tenant_id = $2",
            folder_id,
            tenant_id,
        )
