"""File upload + serve endpoints (file-uploads spec).

Images are stored in blob storage and served back to workspace members. The
use case validates size and sniffs the real image type; this router is thin.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, UploadFile
from pydantic import BaseModel

from cyberarche.adapters.inbound.http.dependencies import Caller, Cases
from cyberarche.domain.ids import WorkspaceId

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}/files", tags=["files"])

# Long-lived: a served file is immutable (unique id per upload).
_CACHE_CONTROL = "private, max-age=31536000, immutable"


class UploadResponse(BaseModel):
    id: str
    url: str
    content_type: str


@router.post("", status_code=201)
async def upload_file(
    workspace_id: str, file: UploadFile, cases: Cases, caller: Caller
) -> UploadResponse:
    uploaded = await cases.files.upload_image(
        caller, WorkspaceId(workspace_id), content=await file.read()
    )
    return UploadResponse(
        id=uploaded.id, url=uploaded.url, content_type=uploaded.content_type
    )


@router.get("/{file_id}")
async def get_file(
    workspace_id: str, file_id: str, cases: Cases, caller: Caller
) -> Response:
    blob = await cases.files.get_file(caller, WorkspaceId(workspace_id), file_id)
    if blob is None:
        raise HTTPException(status_code=404, detail="file not found")
    return Response(
        content=blob.content,
        media_type=blob.content_type,
        headers={"Cache-Control": _CACHE_CONTROL},
    )
