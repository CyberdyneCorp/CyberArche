"""HTTP DTOs. Thin: they mirror domain objects, never leak into use cases."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from cyberarche.application.use_cases.documents import PathCrumb
from cyberarche.domain.documents import Document
from cyberarche.domain.snapshots import BlockDiff, Snapshot
from cyberarche.domain.workspaces import Workspace

# ---- Requests -------------------------------------------------------------


class CreateWorkspaceRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class CreateDocumentRequest(BaseModel):
    workspace_id: str
    title: str = ""
    parent_id: str | None = None
    teamspace_id: str | None = None


class RetitleDocumentRequest(BaseModel):
    title: str


class MoveDocumentRequest(BaseModel):
    parent_id: str | None = None
    position: int = 0


class RecordSnapshotRequest(BaseModel):
    content: dict[str, Any]
    state_vector_b64: str = ""
    label: str | None = None


class RenameSnapshotRequest(BaseModel):
    label: str | None = None


# ---- Responses ------------------------------------------------------------


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    created_by: str
    created_at: datetime
    rag_project_slug: str | None

    @staticmethod
    def from_domain(workspace: Workspace) -> "WorkspaceResponse":
        return WorkspaceResponse(
            id=workspace.id,
            name=workspace.name,
            created_by=workspace.created_by,
            created_at=workspace.created_at,
            rag_project_slug=workspace.rag_project_slug,
        )


class DocumentResponse(BaseModel):
    id: str
    workspace_id: str
    title: str
    parent_id: str | None
    position: int
    created_by: str
    created_at: datetime
    updated_at: datetime
    trashed: bool
    teamspace_id: str | None = None
    folder_id: str | None = None

    @staticmethod
    def from_domain(document: Document) -> "DocumentResponse":
        return DocumentResponse(
            id=document.id,
            workspace_id=document.workspace_id,
            title=document.title,
            parent_id=document.parent_id,
            position=document.position,
            created_by=document.created_by,
            created_at=document.created_at,
            updated_at=document.updated_at,
            trashed=document.trashed,
            teamspace_id=document.teamspace_id,
            folder_id=document.folder_id,
        )


class PathCrumbResponse(BaseModel):
    """One crumb of a document's breadcrumb path (document-breadcrumb change)."""

    kind: str
    id: str
    label: str

    @staticmethod
    def from_domain(crumb: PathCrumb) -> "PathCrumbResponse":
        return PathCrumbResponse(kind=crumb.kind, id=crumb.id, label=crumb.label)


class PurgeResponse(BaseModel):
    """The ids removed by a permanent delete — the document and its subtree."""

    purged: list[str]


class SnapshotResponse(BaseModel):
    id: str
    document_id: str
    seq: int
    created_at: datetime
    restored_from: str | None
    created_by: str | None
    label: str | None = None

    @staticmethod
    def from_domain(snapshot: Snapshot) -> "SnapshotResponse":
        return SnapshotResponse(
            id=snapshot.id,
            document_id=snapshot.document_id,
            seq=snapshot.seq,
            created_at=snapshot.created_at,
            restored_from=snapshot.restored_from,
            created_by=snapshot.created_by,
            label=snapshot.label,
        )


class SnapshotDetailResponse(SnapshotResponse):
    content: dict[str, Any]

    @staticmethod
    def from_domain(snapshot: Snapshot) -> "SnapshotDetailResponse":
        base = SnapshotResponse.from_domain(snapshot)
        return SnapshotDetailResponse(**base.model_dump(), content=snapshot.content)


class BlockDiffResponse(BaseModel):
    """Block-level changes between two versions (version-history spec)."""

    added: list[dict[str, Any]]
    removed: list[dict[str, Any]]
    modified: list[dict[str, Any]]

    @staticmethod
    def from_domain(diff: BlockDiff) -> "BlockDiffResponse":
        return BlockDiffResponse(
            added=diff.added, removed=diff.removed, modified=diff.modified
        )
