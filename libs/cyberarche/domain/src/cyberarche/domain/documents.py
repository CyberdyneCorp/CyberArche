"""Document aggregate (document-model spec).

Documents form a tree: a document's parent is either its workspace (root
document) or another document in the same workspace. Ordering among
siblings is an explicit integer position. Deletion is soft (trash).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime

from cyberarche.domain.errors import ValidationFailed
from cyberarche.domain.ids import (
    CollectionId,
    DocumentId,
    FolderId,
    TeamspaceId,
    TenantId,
    UserId,
    WorkspaceId,
)

MAX_TITLE_LENGTH = 500


@dataclass(frozen=True, slots=True)
class Document:
    id: DocumentId
    workspace_id: WorkspaceId
    tenant_id: TenantId
    title: str
    # None => root document parented by the workspace itself.
    parent_id: DocumentId | None
    position: int
    created_by: UserId
    created_at: datetime
    updated_at: datetime
    trashed: bool = False
    # Parent at the moment of trashing, so restore can put it back.
    trashed_from_parent_id: DocumentId | None = None
    # Optional teamspace of the same workspace (teamspaces spec).
    teamspace_id: TeamspaceId | None = None
    # Optional folder grouping this document (add-folders-and-private).
    folder_id: FolderId | None = None
    # Optional collection this document is a row of (collections-foundation).
    collection_id: CollectionId | None = None
    # Typed property values keyed by PropertyDef.id, when this is a row.
    properties: dict[str, object] = field(default_factory=dict)

    @staticmethod
    def create(
        *,
        id: DocumentId,
        workspace_id: WorkspaceId,
        tenant_id: TenantId,
        title: str,
        parent_id: DocumentId | None,
        position: int,
        created_by: UserId,
        created_at: datetime,
        teamspace_id: TeamspaceId | None = None,
        collection_id: CollectionId | None = None,
    ) -> "Document":
        return Document(
            id=id,
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            title=_valid_title(title),
            parent_id=parent_id,
            position=position,
            created_by=created_by,
            created_at=created_at,
            updated_at=created_at,
            teamspace_id=teamspace_id,
            collection_id=collection_id,
        )

    def retitle(self, title: str, *, now: datetime) -> "Document":
        return replace(self, title=_valid_title(title), updated_at=now)

    def with_properties(
        self, properties: dict[str, object], *, now: datetime
    ) -> "Document":
        """Replace this row's stored property values (collections-foundation)."""
        return replace(self, properties=dict(properties), updated_at=now)

    def moved(
        self, *, parent_id: DocumentId | None, position: int, now: datetime
    ) -> "Document":
        if parent_id == self.id:
            raise ValidationFailed("a document cannot be its own parent")
        return replace(self, parent_id=parent_id, position=position, updated_at=now)

    def trash(self, *, now: datetime) -> "Document":
        return replace(
            self,
            trashed=True,
            trashed_from_parent_id=self.parent_id,
            updated_at=now,
        )

    def restore(self, *, now: datetime) -> "Document":
        return replace(
            self,
            trashed=False,
            parent_id=self.trashed_from_parent_id,
            trashed_from_parent_id=None,
            updated_at=now,
        )


def _valid_title(title: str) -> str:
    title = title.strip()
    if not title:
        title = "Untitled"
    if len(title) > MAX_TITLE_LENGTH:
        raise ValidationFailed(f"document title exceeds {MAX_TITLE_LENGTH} characters")
    return title
