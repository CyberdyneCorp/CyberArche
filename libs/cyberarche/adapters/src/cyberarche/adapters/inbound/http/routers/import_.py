"""Document-import endpoint (document-import spec): upload a file (Markdown /
Word / text / PDF / CSV / Excel / Notion `.zip`) and get back the created
private document(s), each populated with the file's content as editable blocks.
This router is thin: it reads the upload and delegates to the use case."""

from __future__ import annotations

from fastapi import APIRouter, UploadFile

from cyberarche.adapters.inbound.http.dependencies import Caller, Cases
from cyberarche.adapters.inbound.http.schemas import DocumentResponse
from cyberarche.domain.ids import WorkspaceId

router = APIRouter(prefix="/api/v1", tags=["import"])


@router.post("/workspaces/{workspace_id}/import", status_code=201)
async def import_document(
    workspace_id: str, file: UploadFile, cases: Cases, caller: Caller
) -> list[DocumentResponse]:
    """Import an uploaded file into new private document(s)."""
    documents = await cases.document_import.import_upload(
        caller,
        workspace_id=WorkspaceId(workspace_id),
        filename=file.filename or "upload",
        content=await file.read(),
    )
    return [DocumentResponse.from_domain(doc) for doc in documents]
