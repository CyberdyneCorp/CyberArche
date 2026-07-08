"""Knowledge endpoints (rag-knowledge spec): ingest, poll, query, delete."""

from __future__ import annotations

import hmac
from datetime import datetime

from fastapi import APIRouter, Request, UploadFile
from pydantic import BaseModel

from cyberarche.adapters.inbound.http.dependencies import Caller, Cases, get_container
from cyberarche.domain.errors import NotAuthenticated
from cyberarche.domain.ids import WorkspaceId
from cyberarche.application.ports.rag import IngestionRecord, RagQueryMode

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}/knowledge", tags=["knowledge"])
webhook_router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


class IngestionResponse(BaseModel):
    task_id: str
    filename: str
    status: str
    error: str | None
    created_at: datetime

    @staticmethod
    def from_record(record: IngestionRecord) -> "IngestionResponse":
        return IngestionResponse(
            task_id=record.task_id,
            filename=record.filename,
            status=record.status.value,
            error=record.error,
            created_at=record.created_at,
        )


class QueryRequest(BaseModel):
    query: str
    mode: RagQueryMode = RagQueryMode.HYBRID


class QueryResponse(BaseModel):
    result: str
    mode: RagQueryMode


class QueuedIngestionResponse(BaseModel):
    job_id: str
    status: str = "queued"


@router.post("/files", status_code=202)
async def ingest_file(
    workspace_id: str, file: UploadFile, cases: Cases, caller: Caller
) -> IngestionResponse:
    record = await cases.knowledge.ingest_file(
        caller,
        WorkspaceId(workspace_id),
        filename=file.filename or "upload",
        content=await file.read(),
        content_type=file.content_type or "application/octet-stream",
    )
    return IngestionResponse.from_record(record)


@router.post("/files/async", status_code=202)
async def ingest_file_async(
    workspace_id: str, file: UploadFile, cases: Cases, caller: Caller
) -> QueuedIngestionResponse:
    """Queue-backed ingestion: the RAG upload happens on a worker, the
    request returns immediately (architecture-quality spec)."""
    job_id = await cases.knowledge.enqueue_ingestion(
        caller,
        WorkspaceId(workspace_id),
        filename=file.filename or "upload",
        content=await file.read(),
        content_type=file.content_type or "application/octet-stream",
    )
    return QueuedIngestionResponse(job_id=job_id)


@router.get("/files")
async def list_sources(
    workspace_id: str, cases: Cases, caller: Caller
) -> list[IngestionResponse]:
    records = await cases.knowledge.list_sources(caller, WorkspaceId(workspace_id))
    return [IngestionResponse.from_record(r) for r in records]


@router.get("/tasks/{task_id}")
async def task_status(
    workspace_id: str, task_id: str, cases: Cases, caller: Caller
) -> IngestionResponse:
    record = await cases.knowledge.refresh_task(
        caller, WorkspaceId(workspace_id), task_id
    )
    return IngestionResponse.from_record(record)


@router.post("/query")
async def query(
    workspace_id: str, body: QueryRequest, cases: Cases, caller: Caller
) -> QueryResponse:
    result = await cases.knowledge.query(
        caller, WorkspaceId(workspace_id), query=body.query, mode=body.mode
    )
    return QueryResponse(result=result, mode=body.mode)


@router.delete("/files/{filename}", status_code=204)
async def delete_source(
    workspace_id: str, filename: str, cases: Cases, caller: Caller
) -> None:
    await cases.knowledge.delete_source(
        caller, WorkspaceId(workspace_id), filename=filename
    )


# ---- RAG completion webhook ------------------------------------------------


class RagWebhookPayload(BaseModel):
    status: str
    error_message: str | None = None


@webhook_router.post("/rag/{task_id}", status_code=204)
async def rag_task_completed(
    task_id: str, payload: RagWebhookPayload, request: Request
) -> None:
    """Callback from CyberdyneRAG; authenticated by a shared webhook secret."""
    container = get_container(request)
    secret = container.config.rag_webhook_secret
    provided = request.headers.get("x-webhook-secret", "")
    if not secret or not hmac.compare_digest(provided, secret):
        raise NotAuthenticated("bad webhook secret")
    await container.use_cases.knowledge.complete_from_webhook(
        task_id, status=payload.status, error=payload.error_message
    )
