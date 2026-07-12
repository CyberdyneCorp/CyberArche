"""TemplateRepository adapter over the templates table."""

from __future__ import annotations

import json

import asyncpg

from cyberarche.domain.ids import TemplateId, TenantId, UserId, WorkspaceId
from cyberarche.domain.templates import Template


def _from_row(row: asyncpg.Record) -> Template:
    content = row["content"]
    if isinstance(content, str):
        content = json.loads(content)
    return Template(
        id=TemplateId(row["id"]),
        tenant_id=TenantId(row["tenant_id"]),
        workspace_id=WorkspaceId(row["workspace_id"]),
        name=row["name"],
        created_by=UserId(row["created_by"]),
        created_at=row["created_at"],
        content=list(content or []),
    )


class PostgresTemplateRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def add(self, template: Template) -> None:
        await self._pool.execute(
            """
            INSERT INTO templates
                (id, tenant_id, workspace_id, name, created_by, created_at, content)
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
            """,
            template.id,
            template.tenant_id,
            template.workspace_id,
            template.name,
            template.created_by,
            template.created_at,
            json.dumps(template.content),
        )

    async def list_for_workspace(
        self, tenant_id: TenantId, workspace_id: WorkspaceId
    ) -> list[Template]:
        rows = await self._pool.fetch(
            """
            SELECT * FROM templates
            WHERE tenant_id = $1 AND workspace_id = $2
            ORDER BY created_at DESC
            """,
            tenant_id,
            workspace_id,
        )
        return [_from_row(r) for r in rows]

    async def get(
        self, tenant_id: TenantId, template_id: TemplateId
    ) -> Template | None:
        row = await self._pool.fetchrow(
            "SELECT * FROM templates WHERE tenant_id = $1 AND id = $2",
            tenant_id,
            template_id,
        )
        return _from_row(row) if row else None

    async def delete(self, tenant_id: TenantId, template_id: TemplateId) -> None:
        await self._pool.execute(
            "DELETE FROM templates WHERE tenant_id = $1 AND id = $2",
            tenant_id,
            template_id,
        )
