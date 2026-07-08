"""Workspace aggregate (document-model spec).

A workspace belongs to exactly one tenant, derived from verified token
claims — never from request input.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from cyberarche.domain.errors import ValidationFailed
from cyberarche.domain.ids import TenantId, UserId, WorkspaceId

MAX_NAME_LENGTH = 200


@dataclass(frozen=True, slots=True)
class Workspace:
    id: WorkspaceId
    tenant_id: TenantId
    name: str
    created_by: UserId
    created_at: datetime
    # Slug of the isolated CyberdyneRAG project backing this workspace's
    # knowledge (rag-knowledge spec). Provisioned asynchronously.
    rag_project_slug: str | None = None

    @staticmethod
    def create(
        *,
        id: WorkspaceId,
        tenant_id: TenantId,
        name: str,
        created_by: UserId,
        created_at: datetime,
    ) -> "Workspace":
        return Workspace(
            id=id,
            tenant_id=tenant_id,
            name=_valid_name(name),
            created_by=created_by,
            created_at=created_at,
        )

    def rename(self, name: str) -> "Workspace":
        return replace(self, name=_valid_name(name))

    def with_rag_project(self, slug: str) -> "Workspace":
        return replace(self, rag_project_slug=slug)


def _valid_name(name: str) -> str:
    name = name.strip()
    if not name:
        raise ValidationFailed("workspace name must not be empty")
    if len(name) > MAX_NAME_LENGTH:
        raise ValidationFailed(f"workspace name exceeds {MAX_NAME_LENGTH} characters")
    return name
