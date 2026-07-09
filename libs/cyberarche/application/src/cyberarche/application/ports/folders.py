"""Folder repository port (folders spec)."""

from __future__ import annotations

from typing import Protocol

from cyberarche.domain.folders import Folder
from cyberarche.domain.ids import FolderId, TeamspaceId, TenantId, WorkspaceId


class FolderRepository(Protocol):
    async def add(self, folder: Folder) -> None: ...

    async def get(self, tenant_id: TenantId, folder_id: FolderId) -> Folder | None: ...

    async def list_for_workspace(
        self, tenant_id: TenantId, workspace_id: WorkspaceId
    ) -> list[Folder]:
        """Every folder in the workspace; the use case scopes visibility."""
        ...

    async def list_for_teamspace(
        self, tenant_id: TenantId, teamspace_id: TeamspaceId
    ) -> list[Folder]: ...

    async def update(self, folder: Folder) -> None: ...

    async def delete(self, tenant_id: TenantId, folder_id: FolderId) -> None:
        """Remove the folder (and, by cascade, its sub-folders). Documents in it
        are detached, not deleted."""
        ...
