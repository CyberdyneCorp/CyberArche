"""Collection repository port (collections-foundation spec)."""

from __future__ import annotations

from typing import Protocol

from cyberarche.domain.collections import Collection
from cyberarche.domain.ids import CollectionId, TenantId, WorkspaceId


class CollectionRepository(Protocol):
    async def add(self, collection: Collection) -> None: ...

    async def get(
        self, tenant_id: TenantId, collection_id: CollectionId
    ) -> Collection | None: ...

    async def list_in_workspace(
        self, tenant_id: TenantId, workspace_id: WorkspaceId
    ) -> list[Collection]: ...

    async def update(self, collection: Collection) -> None:
        """Replace the collection's name, property schema, and views."""
        ...

    async def delete(self, tenant_id: TenantId, collection_id: CollectionId) -> None: ...
