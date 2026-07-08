"""Repository ports for the document model."""

from __future__ import annotations

from typing import Protocol

from cyberarche.domain.documents import Document
from cyberarche.domain.ids import DocumentId, SnapshotId, TenantId, UserId, WorkspaceId
from cyberarche.domain.memberships import DocumentGrant, WorkspaceMembership
from cyberarche.domain.snapshots import Snapshot
from cyberarche.domain.workspaces import Workspace


class WorkspaceRepository(Protocol):
    async def add(self, workspace: Workspace) -> None: ...

    async def get(self, tenant_id: TenantId, workspace_id: WorkspaceId) -> Workspace | None: ...

    async def list_for_tenant(self, tenant_id: TenantId) -> list[Workspace]: ...

    async def update(self, workspace: Workspace) -> None: ...


class DocumentRepository(Protocol):
    async def add(self, document: Document) -> None: ...

    async def get(self, tenant_id: TenantId, document_id: DocumentId) -> Document | None: ...

    async def get_any_tenant(self, document_id: DocumentId) -> Document | None:
        """Tenant-agnostic lookup — ONLY for share-link resolution, where
        access is decided by an explicit grant instead of tenant scope."""
        ...

    async def children(
        self,
        tenant_id: TenantId,
        workspace_id: WorkspaceId,
        parent_id: DocumentId | None,
        *,
        include_trashed: bool = False,
    ) -> list[Document]:
        """Ordered siblings under a parent (None => workspace roots)."""
        ...

    async def list_trashed(
        self, tenant_id: TenantId, workspace_id: WorkspaceId
    ) -> list[Document]: ...

    async def update(self, document: Document) -> None: ...

    async def update_many(self, documents: list[Document]) -> None: ...

    async def search_by_title(
        self, tenant_id: TenantId, query: str, *, limit: int = 20
    ) -> list[Document]:
        """Case-insensitive title match within a tenant (no trashed docs)."""
        ...


class SnapshotRepository(Protocol):
    async def add(self, snapshot: Snapshot) -> None: ...

    async def get(self, document_id: DocumentId, snapshot_id: SnapshotId) -> Snapshot | None: ...

    async def list_for_document(self, document_id: DocumentId) -> list[Snapshot]: ...

    async def latest(self, document_id: DocumentId) -> Snapshot | None: ...


class MembershipRepository(Protocol):
    async def add_workspace_member(self, membership: WorkspaceMembership) -> None: ...

    async def workspace_role(
        self, workspace_id: WorkspaceId, user_id: UserId
    ) -> WorkspaceMembership | None: ...

    async def add_document_grant(self, grant: DocumentGrant) -> None: ...

    async def document_grant(
        self, document_id: DocumentId, user_id: UserId
    ) -> DocumentGrant | None: ...
