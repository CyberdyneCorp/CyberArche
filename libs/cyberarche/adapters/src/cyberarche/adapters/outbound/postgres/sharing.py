"""ShareLink and Comment repositories over Postgres."""

from __future__ import annotations

import asyncpg

from cyberarche.domain.ids import DocumentId, ShareLinkId, UserId
from cyberarche.domain.sharing import Comment, ShareLink, SharePermission


def _link_from_row(row: asyncpg.Record) -> ShareLink:
    return ShareLink(
        id=ShareLinkId(row["id"]),
        document_id=DocumentId(row["document_id"]),
        permission=SharePermission(row["permission"]),
        created_by=UserId(row["created_by"]),
        created_at=row["created_at"],
        expires_at=row["expires_at"],
        revoked_at=row["revoked_at"],
    )


class PostgresShareLinkRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def add(self, link: ShareLink) -> None:
        await self._pool.execute(
            """
            INSERT INTO share_links
                (id, document_id, permission, created_by, created_at, expires_at, revoked_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            link.id,
            link.document_id,
            link.permission.value,
            link.created_by,
            link.created_at,
            link.expires_at,
            link.revoked_at,
        )

    async def get(self, link_id: ShareLinkId) -> ShareLink | None:
        row = await self._pool.fetchrow(
            "SELECT * FROM share_links WHERE id = $1", link_id
        )
        return _link_from_row(row) if row else None

    async def list_for_document(self, document_id: DocumentId) -> list[ShareLink]:
        rows = await self._pool.fetch(
            "SELECT * FROM share_links WHERE document_id = $1 ORDER BY created_at",
            document_id,
        )
        return [_link_from_row(r) for r in rows]

    async def update(self, link: ShareLink) -> None:
        await self._pool.execute(
            "UPDATE share_links SET expires_at = $2, revoked_at = $3 WHERE id = $1",
            link.id,
            link.expires_at,
            link.revoked_at,
        )


def _comment_from_row(row: asyncpg.Record) -> Comment:
    return Comment(
        id=row["id"],
        document_id=DocumentId(row["document_id"]),
        block_id=row["block_id"],
        author_id=UserId(row["author_id"]),
        body=row["body"],
        created_at=row["created_at"],
        resolved_at=row["resolved_at"],
        resolved_by=UserId(row["resolved_by"]) if row["resolved_by"] else None,
    )


class PostgresCommentRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def add(self, comment: Comment) -> None:
        await self._pool.execute(
            """
            INSERT INTO comments
                (id, document_id, block_id, author_id, body, created_at,
                 resolved_at, resolved_by)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            comment.id,
            comment.document_id,
            comment.block_id,
            comment.author_id,
            comment.body,
            comment.created_at,
            comment.resolved_at,
            comment.resolved_by,
        )

    async def get(self, document_id: DocumentId, comment_id: str) -> Comment | None:
        row = await self._pool.fetchrow(
            "SELECT * FROM comments WHERE id = $1 AND document_id = $2",
            comment_id,
            document_id,
        )
        return _comment_from_row(row) if row else None

    async def list_for_document(self, document_id: DocumentId) -> list[Comment]:
        rows = await self._pool.fetch(
            "SELECT * FROM comments WHERE document_id = $1 ORDER BY created_at",
            document_id,
        )
        return [_comment_from_row(r) for r in rows]

    async def update(self, comment: Comment) -> None:
        await self._pool.execute(
            "UPDATE comments SET resolved_at = $2, resolved_by = $3 WHERE id = $1",
            comment.id,
            comment.resolved_at,
            comment.resolved_by,
        )
