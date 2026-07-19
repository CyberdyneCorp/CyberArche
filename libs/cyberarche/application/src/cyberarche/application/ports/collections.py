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

    async def list_all(self) -> list[Collection]:
        """Every collection across all tenants — for the background reminder
        sweep (mirrors how the digest enumerates cross-tenant)."""
        ...

    async def update(self, collection: Collection) -> None:
        """Replace the collection's name, property schema, and views."""
        ...

    async def delete(self, tenant_id: TenantId, collection_id: CollectionId) -> None: ...


class ReminderStateRepository(Protocol):
    """De-dup store so a date reminder fires at most once per row, property, and
    date value. Changing the stored date value re-arms the reminder."""

    async def was_reminded(
        self, document_id: str, property_id: str, value: str
    ) -> bool:
        """True iff a reminder was already sent for this exact date value."""
        ...

    async def mark_reminded(
        self, document_id: str, property_id: str, value: str
    ) -> None:
        """Record that a reminder fired for this row/property's date value
        (upsert: a new value replaces the old one)."""
        ...
