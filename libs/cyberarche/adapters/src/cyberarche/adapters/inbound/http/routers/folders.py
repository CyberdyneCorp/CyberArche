"""Folder endpoints (folders spec) + document placement and private listing."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from cyberarche.adapters.inbound.http.dependencies import Caller, Cases
from cyberarche.adapters.inbound.http.schemas import DocumentResponse
from cyberarche.domain.folders import Folder
from cyberarche.domain.ids import DocumentId, FolderId, TeamspaceId, WorkspaceId

router = APIRouter(tags=["folders"])


class CreateFolderRequest(BaseModel):
    name: str
    teamspace_id: str | None = None
    parent_folder_id: str | None = None


class RenameFolderRequest(BaseModel):
    name: str


class FolderResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    teamspace_id: str | None
    parent_folder_id: str | None
    created_by: str
    created_at: datetime

    @staticmethod
    def from_domain(folder: Folder) -> "FolderResponse":
        return FolderResponse(
            id=folder.id,
            workspace_id=folder.workspace_id,
            name=folder.name,
            teamspace_id=folder.teamspace_id,
            parent_folder_id=folder.parent_folder_id,
            created_by=folder.created_by,
            created_at=folder.created_at,
        )


@router.post("/api/v1/workspaces/{workspace_id}/folders", status_code=201)
async def create_folder(
    workspace_id: str, body: CreateFolderRequest, cases: Cases, caller: Caller
) -> FolderResponse:
    folder = await cases.folders.create(
        caller,
        WorkspaceId(workspace_id),
        name=body.name,
        teamspace_id=TeamspaceId(body.teamspace_id) if body.teamspace_id else None,
        parent_folder_id=(
            FolderId(body.parent_folder_id) if body.parent_folder_id else None
        ),
    )
    return FolderResponse.from_domain(folder)


@router.get("/api/v1/workspaces/{workspace_id}/folders")
async def list_folders(
    workspace_id: str, cases: Cases, caller: Caller
) -> list[FolderResponse]:
    folders = await cases.folders.list_for_workspace(caller, WorkspaceId(workspace_id))
    return [FolderResponse.from_domain(f) for f in folders]


@router.patch("/api/v1/folders/{folder_id}")
async def rename_folder(
    folder_id: str, body: RenameFolderRequest, cases: Cases, caller: Caller
) -> FolderResponse:
    folder = await cases.folders.rename(caller, FolderId(folder_id), name=body.name)
    return FolderResponse.from_domain(folder)


@router.delete("/api/v1/folders/{folder_id}", status_code=204)
async def delete_folder(folder_id: str, cases: Cases, caller: Caller) -> None:
    await cases.folders.delete(caller, FolderId(folder_id))


@router.get("/api/v1/folders/{folder_id}/documents")
async def folder_documents(
    folder_id: str, cases: Cases, caller: Caller
) -> list[DocumentResponse]:
    documents = await cases.documents.list_for_folder(caller, FolderId(folder_id))
    return [DocumentResponse.from_domain(d) for d in documents]


@router.get("/api/v1/folders/{folder_id}/graph")
async def folder_graph(folder_id: str, cases: Cases, caller: Caller) -> dict:
    """The `[[wikilink]]` graph of this folder's documents ({nodes, edges})."""
    graph = await cases.links.graph(caller, folder_id=FolderId(folder_id))
    return asdict(graph)


@router.get("/api/v1/folders/{folder_id}/graph/inferred")
async def folder_inferred_graph(folder_id: str, cases: Cases, caller: Caller) -> dict:
    """The graph with AI-inferred typed edges added (cached per document)."""
    graph = await cases.links.inferred_graph(caller, folder_id=FolderId(folder_id))
    return asdict(graph)


class PlaceDocumentRequest(BaseModel):
    # A folder, or a teamspace, or (both null) the private space.
    folder_id: str | None = None
    teamspace_id: str | None = None


@router.post("/api/v1/documents/{document_id}/location")
async def place_document(
    document_id: str, body: PlaceDocumentRequest, cases: Cases, caller: Caller
) -> DocumentResponse:
    if body.folder_id:
        document = await cases.documents.place_in_folder(
            caller, DocumentId(document_id), FolderId(body.folder_id)
        )
    elif body.teamspace_id:
        document = await cases.documents.move_to_teamspace(
            caller, DocumentId(document_id), TeamspaceId(body.teamspace_id)
        )
    else:
        document = await cases.documents.move_to_private(
            caller, DocumentId(document_id)
        )
    return DocumentResponse.from_domain(document)


@router.get("/api/v1/workspaces/{workspace_id}/private")
async def list_private(
    workspace_id: str, cases: Cases, caller: Caller
) -> list[DocumentResponse]:
    documents = await cases.documents.list_private(
        caller, workspace_id=WorkspaceId(workspace_id)
    )
    return [DocumentResponse.from_domain(d) for d in documents]


@router.get("/api/v1/workspaces/{workspace_id}/trash")
async def list_trash(
    workspace_id: str, cases: Cases, caller: Caller
) -> list[DocumentResponse]:
    documents = await cases.documents.list_trashed(
        caller, workspace_id=WorkspaceId(workspace_id)
    )
    return [DocumentResponse.from_domain(d) for d in documents]


@router.get("/api/v1/workspaces/{workspace_id}/search")
async def search_documents(
    workspace_id: str, cases: Cases, caller: Caller, q: str = "", limit: int = 50
) -> list[DocumentResponse]:
    """Title search within the workspace (empty q returns all accessible docs).
    Backs the command palette and the wikilink title index."""
    documents = await cases.documents.search_in_workspace(
        caller, WorkspaceId(workspace_id), query=q, limit=limit
    )
    return [DocumentResponse.from_domain(d) for d in documents]


class SearchHitResponse(BaseModel):
    id: str
    title: str
    field: str  # "title" | "content"
    snippet: str


@router.get("/api/v1/workspaces/{workspace_id}/search/content")
async def search_content(
    workspace_id: str, cases: Cases, caller: Caller, q: str = "", limit: int = 20
) -> list[SearchHitResponse]:
    """Full-text search over document titles and block content, each hit marked
    with the field it matched and (for content) a surrounding snippet."""
    hits = await cases.search.search(
        caller, WorkspaceId(workspace_id), query=q, limit=limit
    )
    return [
        SearchHitResponse(
            id=hit.document.id,
            title=hit.document.title,
            field=hit.field,
            snippet=hit.snippet,
        )
        for hit in hits
    ]
