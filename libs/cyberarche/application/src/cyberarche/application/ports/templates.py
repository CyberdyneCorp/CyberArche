"""Template repository port (templates spec)."""

from __future__ import annotations

from typing import Protocol

from cyberarche.domain.ids import TemplateId, TenantId, WorkspaceId
from cyberarche.domain.templates import Template


class TemplateRepository(Protocol):
    async def add(self, template: Template) -> None: ...

    async def list_for_workspace(
        self, tenant_id: TenantId, workspace_id: WorkspaceId
    ) -> list[Template]:
        """The workspace's templates, newest first."""
        ...

    async def get(
        self, tenant_id: TenantId, template_id: TemplateId
    ) -> Template | None: ...

    async def delete(self, tenant_id: TenantId, template_id: TemplateId) -> None: ...
