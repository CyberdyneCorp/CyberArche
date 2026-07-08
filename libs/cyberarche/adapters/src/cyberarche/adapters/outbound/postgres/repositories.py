"""Postgres repositories (asyncpg). Thin row<->aggregate mapping only.

Tenant scoping is passed explicitly in every query; Postgres RLS
(db/migrations) provides defense-in-depth behind it.
"""

from __future__ import annotations

import json
from typing import Any

import asyncpg

from cyberarche.domain.documents import Document
from cyberarche.domain.ids import (
    DocumentId,
    SnapshotId,
    TenantId,
    UserId,
    WorkspaceId,
)
from cyberarche.domain.memberships import DocumentGrant, Role, WorkspaceMembership
from cyberarche.domain.snapshots import Snapshot
from cyberarche.domain.workspaces import Workspace


def _workspace_from_row(row: asyncpg.Record) -> Workspace:
    return Workspace(
        id=WorkspaceId(row["id"]),
        tenant_id=TenantId(row["tenant_id"]),
        name=row["name"],
        created_by=UserId(row["created_by"]),
        created_at=row["created_at"],
        rag_project_slug=row["rag_project_slug"],
    )


def _document_from_row(row: asyncpg.Record) -> Document:
    return Document(
        id=DocumentId(row["id"]),
        workspace_id=WorkspaceId(row["workspace_id"]),
        tenant_id=TenantId(row["tenant_id"]),
        title=row["title"],
        parent_id=DocumentId(row["parent_id"]) if row["parent_id"] else None,
        position=row["position"],
        created_by=UserId(row["created_by"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        trashed=row["trashed"],
        trashed_from_parent_id=(
            DocumentId(row["trashed_from_parent_id"])
            if row["trashed_from_parent_id"]
            else None
        ),
    )


def _snapshot_from_row(row: asyncpg.Record) -> Snapshot:
    return Snapshot(
        id=SnapshotId(row["id"]),
        document_id=DocumentId(row["document_id"]),
        seq=row["seq"],
        content=json.loads(row["content"]),
        state_vector=bytes(row["state_vector"]),
        created_at=row["created_at"],
        restored_from=SnapshotId(row["restored_from"]) if row["restored_from"] else None,
        created_by=UserId(row["created_by"]) if row["created_by"] else None,
    )


class PostgresWorkspaceRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def add(self, workspace: Workspace) -> None:
        await self._pool.execute(
            """
            INSERT INTO workspaces (id, tenant_id, name, created_by, created_at, rag_project_slug)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            workspace.id,
            workspace.tenant_id,
            workspace.name,
            workspace.created_by,
            workspace.created_at,
            workspace.rag_project_slug,
        )

    async def get(self, tenant_id: TenantId, workspace_id: WorkspaceId) -> Workspace | None:
        row = await self._pool.fetchrow(
            "SELECT * FROM workspaces WHERE id = $1 AND tenant_id = $2",
            workspace_id,
            tenant_id,
        )
        return _workspace_from_row(row) if row else None

    async def list_for_tenant(self, tenant_id: TenantId) -> list[Workspace]:
        rows = await self._pool.fetch(
            "SELECT * FROM workspaces WHERE tenant_id = $1 ORDER BY created_at",
            tenant_id,
        )
        return [_workspace_from_row(r) for r in rows]

    async def update(self, workspace: Workspace) -> None:
        await self._pool.execute(
            "UPDATE workspaces SET name = $2, rag_project_slug = $3 WHERE id = $1",
            workspace.id,
            workspace.name,
            workspace.rag_project_slug,
        )


class PostgresDocumentRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def add(self, document: Document) -> None:
        await self._pool.execute(
            """
            INSERT INTO documents
                (id, workspace_id, tenant_id, title, parent_id, position,
                 created_by, created_at, updated_at, trashed, trashed_from_parent_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            """,
            *_document_params(document),
        )

    async def get(self, tenant_id: TenantId, document_id: DocumentId) -> Document | None:
        row = await self._pool.fetchrow(
            "SELECT * FROM documents WHERE id = $1 AND tenant_id = $2",
            document_id,
            tenant_id,
        )
        return _document_from_row(row) if row else None

    async def children(
        self,
        tenant_id: TenantId,
        workspace_id: WorkspaceId,
        parent_id: DocumentId | None,
        *,
        include_trashed: bool = False,
    ) -> list[Document]:
        rows = await self._pool.fetch(
            """
            SELECT * FROM documents
            WHERE tenant_id = $1 AND workspace_id = $2
              AND parent_id IS NOT DISTINCT FROM $3
              AND (trashed = FALSE OR $4)
            ORDER BY position
            """,
            tenant_id,
            workspace_id,
            parent_id,
            include_trashed,
        )
        return [_document_from_row(r) for r in rows]

    async def list_trashed(
        self, tenant_id: TenantId, workspace_id: WorkspaceId
    ) -> list[Document]:
        rows = await self._pool.fetch(
            """
            SELECT * FROM documents
            WHERE tenant_id = $1 AND workspace_id = $2 AND trashed = TRUE
            ORDER BY updated_at DESC
            """,
            tenant_id,
            workspace_id,
        )
        return [_document_from_row(r) for r in rows]

    async def update(self, document: Document) -> None:
        await self._pool.execute(
            """
            UPDATE documents SET
                title = $4, parent_id = $5, position = $6, updated_at = $9,
                trashed = $10, trashed_from_parent_id = $11
            WHERE id = $1
            """,
            *_document_params(document),
        )

    async def search_by_title(
        self, tenant_id: TenantId, query: str, *, limit: int = 20
    ) -> list[Document]:
        rows = await self._pool.fetch(
            """
            SELECT * FROM documents
            WHERE tenant_id = $1 AND trashed = FALSE AND title ILIKE '%' || $2 || '%'
            ORDER BY title
            LIMIT $3
            """,
            tenant_id,
            query,
            limit,
        )
        return [_document_from_row(r) for r in rows]

    async def update_many(self, documents: list[Document]) -> None:
        async with self._pool.acquire() as connection:
            async with connection.transaction():
                for document in documents:
                    await connection.execute(
                        """
                        UPDATE documents SET
                            title = $4, parent_id = $5, position = $6, updated_at = $9,
                            trashed = $10, trashed_from_parent_id = $11
                        WHERE id = $1
                        """,
                        *_document_params(document),
                    )


def _document_params(document: Document) -> tuple[Any, ...]:
    return (
        document.id,
        document.workspace_id,
        document.tenant_id,
        document.title,
        document.parent_id,
        document.position,
        document.created_by,
        document.created_at,
        document.updated_at,
        document.trashed,
        document.trashed_from_parent_id,
    )


class PostgresSnapshotRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def add(self, snapshot: Snapshot) -> None:
        await self._pool.execute(
            """
            INSERT INTO snapshots
                (id, document_id, seq, content, state_vector, created_at,
                 restored_from, created_by)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            snapshot.id,
            snapshot.document_id,
            snapshot.seq,
            json.dumps(snapshot.content),
            snapshot.state_vector,
            snapshot.created_at,
            snapshot.restored_from,
            snapshot.created_by,
        )

    async def get(self, document_id: DocumentId, snapshot_id: SnapshotId) -> Snapshot | None:
        row = await self._pool.fetchrow(
            "SELECT * FROM snapshots WHERE id = $1 AND document_id = $2",
            snapshot_id,
            document_id,
        )
        return _snapshot_from_row(row) if row else None

    async def list_for_document(self, document_id: DocumentId) -> list[Snapshot]:
        rows = await self._pool.fetch(
            "SELECT * FROM snapshots WHERE document_id = $1 ORDER BY seq",
            document_id,
        )
        return [_snapshot_from_row(r) for r in rows]

    async def latest(self, document_id: DocumentId) -> Snapshot | None:
        row = await self._pool.fetchrow(
            "SELECT * FROM snapshots WHERE document_id = $1 ORDER BY seq DESC LIMIT 1",
            document_id,
        )
        return _snapshot_from_row(row) if row else None


class PostgresMembershipRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def add_workspace_member(self, membership: WorkspaceMembership) -> None:
        await self._pool.execute(
            """
            INSERT INTO workspace_memberships (workspace_id, user_id, role, granted_at)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (workspace_id, user_id) DO UPDATE
                SET role = EXCLUDED.role, granted_at = EXCLUDED.granted_at
            """,
            membership.workspace_id,
            membership.user_id,
            membership.role.value,
            membership.granted_at,
        )

    async def workspace_role(
        self, workspace_id: WorkspaceId, user_id: UserId
    ) -> WorkspaceMembership | None:
        row = await self._pool.fetchrow(
            """
            SELECT * FROM workspace_memberships
            WHERE workspace_id = $1 AND user_id = $2
            """,
            workspace_id,
            user_id,
        )
        if row is None:
            return None
        return WorkspaceMembership(
            workspace_id=WorkspaceId(row["workspace_id"]),
            user_id=UserId(row["user_id"]),
            role=Role(row["role"]),
            granted_at=row["granted_at"],
        )

    async def add_document_grant(self, grant: DocumentGrant) -> None:
        await self._pool.execute(
            """
            INSERT INTO document_grants (document_id, user_id, role, granted_at)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (document_id, user_id) DO UPDATE
                SET role = EXCLUDED.role, granted_at = EXCLUDED.granted_at
            """,
            grant.document_id,
            grant.user_id,
            grant.role.value,
            grant.granted_at,
        )

    async def document_grant(
        self, document_id: DocumentId, user_id: UserId
    ) -> DocumentGrant | None:
        row = await self._pool.fetchrow(
            "SELECT * FROM document_grants WHERE document_id = $1 AND user_id = $2",
            document_id,
            user_id,
        )
        if row is None:
            return None
        return DocumentGrant(
            document_id=DocumentId(row["document_id"]),
            user_id=UserId(row["user_id"]),
            role=Role(row["role"]),
            granted_at=row["granted_at"],
        )
