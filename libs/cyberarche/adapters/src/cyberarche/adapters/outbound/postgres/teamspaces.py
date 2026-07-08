"""Teamspace and favourite repositories over Postgres."""

from __future__ import annotations

import asyncpg

from cyberarche.domain.ids import (
    DocumentId,
    TeamspaceId,
    TenantId,
    UserId,
    WorkspaceId,
)
from cyberarche.domain.memberships import Role
from cyberarche.domain.teamspaces import Teamspace, TeamspaceMembership


def _teamspace_from_row(row: asyncpg.Record) -> Teamspace:
    return Teamspace(
        id=TeamspaceId(row["id"]),
        workspace_id=WorkspaceId(row["workspace_id"]),
        tenant_id=TenantId(row["tenant_id"]),
        name=row["name"],
        icon=row["icon"],
        created_by=UserId(row["created_by"]),
        created_at=row["created_at"],
    )


def _membership_from_row(row: asyncpg.Record) -> TeamspaceMembership:
    return TeamspaceMembership(
        teamspace_id=TeamspaceId(row["teamspace_id"]),
        user_id=UserId(row["user_id"]),
        role=Role(row["role"]),
        granted_at=row["granted_at"],
    )


class PostgresTeamspaceRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def add(self, teamspace: Teamspace) -> None:
        await self._pool.execute(
            """
            INSERT INTO teamspaces
                (id, workspace_id, tenant_id, name, icon, created_by, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            teamspace.id,
            teamspace.workspace_id,
            teamspace.tenant_id,
            teamspace.name,
            teamspace.icon,
            teamspace.created_by,
            teamspace.created_at,
        )

    async def get(
        self, tenant_id: TenantId, teamspace_id: TeamspaceId
    ) -> Teamspace | None:
        row = await self._pool.fetchrow(
            "SELECT * FROM teamspaces WHERE id = $1 AND tenant_id = $2",
            teamspace_id,
            tenant_id,
        )
        return _teamspace_from_row(row) if row else None

    async def list_for_workspace(
        self, tenant_id: TenantId, workspace_id: WorkspaceId
    ) -> list[Teamspace]:
        rows = await self._pool.fetch(
            """
            SELECT * FROM teamspaces
            WHERE tenant_id = $1 AND workspace_id = $2
            ORDER BY created_at
            """,
            tenant_id,
            workspace_id,
        )
        return [_teamspace_from_row(r) for r in rows]

    async def add_member(self, membership: TeamspaceMembership) -> None:
        await self._pool.execute(
            """
            INSERT INTO teamspace_memberships (teamspace_id, user_id, role, granted_at)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (teamspace_id, user_id) DO UPDATE
                SET role = EXCLUDED.role, granted_at = EXCLUDED.granted_at
            """,
            membership.teamspace_id,
            membership.user_id,
            membership.role.value,
            membership.granted_at,
        )

    async def remove_member(self, teamspace_id: TeamspaceId, user_id: UserId) -> None:
        await self._pool.execute(
            "DELETE FROM teamspace_memberships WHERE teamspace_id = $1 AND user_id = $2",
            teamspace_id,
            user_id,
        )

    async def member_role(
        self, teamspace_id: TeamspaceId, user_id: UserId
    ) -> TeamspaceMembership | None:
        row = await self._pool.fetchrow(
            """
            SELECT * FROM teamspace_memberships
            WHERE teamspace_id = $1 AND user_id = $2
            """,
            teamspace_id,
            user_id,
        )
        return _membership_from_row(row) if row else None

    async def members(self, teamspace_id: TeamspaceId) -> list[TeamspaceMembership]:
        rows = await self._pool.fetch(
            "SELECT * FROM teamspace_memberships WHERE teamspace_id = $1 ORDER BY granted_at",
            teamspace_id,
        )
        return [_membership_from_row(r) for r in rows]

    async def teamspaces_for_user(
        self, tenant_id: TenantId, workspace_id: WorkspaceId, user_id: UserId
    ) -> list[Teamspace]:
        rows = await self._pool.fetch(
            """
            SELECT t.* FROM teamspaces t
            JOIN teamspace_memberships m ON m.teamspace_id = t.id
            WHERE t.tenant_id = $1 AND t.workspace_id = $2 AND m.user_id = $3
            ORDER BY t.created_at
            """,
            tenant_id,
            workspace_id,
            user_id,
        )
        return [_teamspace_from_row(r) for r in rows]


class PostgresFavoriteRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def add(self, user_id: UserId, document_id: DocumentId) -> None:
        await self._pool.execute(
            """
            INSERT INTO favorites (user_id, document_id) VALUES ($1, $2)
            ON CONFLICT (user_id, document_id) DO NOTHING
            """,
            user_id,
            document_id,
        )

    async def remove(self, user_id: UserId, document_id: DocumentId) -> None:
        await self._pool.execute(
            "DELETE FROM favorites WHERE user_id = $1 AND document_id = $2",
            user_id,
            document_id,
        )

    async def list_for_user(self, user_id: UserId) -> list[DocumentId]:
        rows = await self._pool.fetch(
            "SELECT document_id FROM favorites WHERE user_id = $1 ORDER BY created_at",
            user_id,
        )
        return [DocumentId(r["document_id"]) for r in rows]

    async def is_favorite(self, user_id: UserId, document_id: DocumentId) -> bool:
        return bool(
            await self._pool.fetchval(
                "SELECT 1 FROM favorites WHERE user_id = $1 AND document_id = $2",
                user_id,
                document_id,
            )
        )
