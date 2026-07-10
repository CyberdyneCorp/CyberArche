from __future__ import annotations

import base64

from fastapi import APIRouter

from cyberarche.adapters.inbound.http.dependencies import Caller, Cases
from cyberarche.adapters.inbound.http.schemas import (
    CreateDocumentRequest,
    DocumentResponse,
    MoveDocumentRequest,
    PurgeResponse,
    RecordSnapshotRequest,
    RetitleDocumentRequest,
    SnapshotDetailResponse,
    SnapshotResponse,
)
from cyberarche.domain.ids import DocumentId, SnapshotId, TeamspaceId, WorkspaceId

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


@router.post("", status_code=201)
async def create_document(
    body: CreateDocumentRequest, cases: Cases, caller: Caller
) -> DocumentResponse:
    document = await cases.documents.create(
        caller,
        workspace_id=WorkspaceId(body.workspace_id),
        title=body.title,
        parent_id=DocumentId(body.parent_id) if body.parent_id else None,
        teamspace_id=TeamspaceId(body.teamspace_id) if body.teamspace_id else None,
    )
    return DocumentResponse.from_domain(document)


@router.get("/{document_id}")
async def get_document(document_id: str, cases: Cases, caller: Caller) -> DocumentResponse:
    document = await cases.documents.get(caller, DocumentId(document_id))
    return DocumentResponse.from_domain(document)


@router.get("/{document_id}/backlinks")
async def document_backlinks(
    document_id: str, cases: Cases, caller: Caller
) -> list[DocumentResponse]:
    """Documents that reference this one via a `[[title]]` wikilink."""
    documents = await cases.links.backlinks(caller, DocumentId(document_id))
    return [DocumentResponse.from_domain(d) for d in documents]


@router.get("")
async def list_children(
    workspace_id: str,
    cases: Cases,
    caller: Caller,
    parent_id: str | None = None,
) -> list[DocumentResponse]:
    documents = await cases.documents.children(
        caller,
        workspace_id=WorkspaceId(workspace_id),
        parent_id=DocumentId(parent_id) if parent_id else None,
    )
    return [DocumentResponse.from_domain(d) for d in documents]


@router.patch("/{document_id}/title")
async def retitle_document(
    document_id: str, body: RetitleDocumentRequest, cases: Cases, caller: Caller
) -> DocumentResponse:
    document = await cases.documents.retitle(
        caller, DocumentId(document_id), title=body.title
    )
    return DocumentResponse.from_domain(document)


@router.post("/{document_id}/move")
async def move_document(
    document_id: str, body: MoveDocumentRequest, cases: Cases, caller: Caller
) -> DocumentResponse:
    document = await cases.documents.move(
        caller,
        DocumentId(document_id),
        parent_id=DocumentId(body.parent_id) if body.parent_id else None,
        position=body.position,
    )
    return DocumentResponse.from_domain(document)


@router.delete("/{document_id}")
async def trash_document(document_id: str, cases: Cases, caller: Caller) -> DocumentResponse:
    document = await cases.documents.trash(caller, DocumentId(document_id))
    return DocumentResponse.from_domain(document)


@router.post("/{document_id}/restore")
async def restore_document(
    document_id: str, cases: Cases, caller: Caller
) -> DocumentResponse:
    document = await cases.documents.restore(caller, DocumentId(document_id))
    return DocumentResponse.from_domain(document)


@router.delete("/{document_id}/trash")
async def purge_document(
    document_id: str, cases: Cases, caller: Caller
) -> PurgeResponse:
    """Permanently delete a trashed document and its subtree. The soft-delete
    (move to trash) stays on `DELETE /{document_id}`."""
    purged = await cases.documents.purge(caller, DocumentId(document_id))
    return PurgeResponse(purged=[str(document_id) for document_id in purged])


# ---- Snapshots -------------------------------------------------------------


@router.post("/{document_id}/snapshots", status_code=201)
async def record_snapshot(
    document_id: str, body: RecordSnapshotRequest, cases: Cases, caller: Caller
) -> SnapshotResponse:
    snapshot = await cases.snapshots.record(
        caller,
        DocumentId(document_id),
        content=body.content,
        state_vector=base64.b64decode(body.state_vector_b64 or b""),
    )
    return SnapshotResponse.from_domain(snapshot)


@router.get("/{document_id}/snapshots")
async def list_snapshots(
    document_id: str, cases: Cases, caller: Caller
) -> list[SnapshotResponse]:
    snapshots = await cases.snapshots.list(caller, DocumentId(document_id))
    return [SnapshotResponse.from_domain(s) for s in snapshots]


@router.post("/{document_id}/snapshots/{snapshot_id}/restore")
async def restore_snapshot(
    document_id: str, snapshot_id: str, cases: Cases, caller: Caller
) -> SnapshotDetailResponse:
    snapshot = await cases.snapshots.restore(
        caller, DocumentId(document_id), SnapshotId(snapshot_id)
    )
    return SnapshotDetailResponse.from_domain(snapshot)
