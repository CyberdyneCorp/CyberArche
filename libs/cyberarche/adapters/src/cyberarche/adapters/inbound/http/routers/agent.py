"""Agent endpoints (ai-agent spec): ask, summarize, draft, ingest, history."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, UploadFile
from pydantic import BaseModel

from cyberarche.adapters.inbound.http.dependencies import Caller, Cases
from cyberarche.application.ports.agent import AgentRun
from cyberarche.domain.ids import DocumentId

router = APIRouter(prefix="/api/v1/documents/{document_id}/agent", tags=["agent"])


class AskRequest(BaseModel):
    instruction: str


class AskResponse(BaseModel):
    answer: str


class BlocksResponse(BaseModel):
    blocks: list[dict]
    inserted: bool = False


class InsertBlocksRequest(BaseModel):
    blocks: list[dict]


class AgentRunResponse(BaseModel):
    id: str
    user_id: str
    model: str
    prompt: str
    tools_used: list[str]
    outcome: str | None
    started_at: datetime | None

    @staticmethod
    def from_domain(run: AgentRun) -> "AgentRunResponse":
        return AgentRunResponse(
            id=run.id,
            user_id=run.user_id,
            model=run.model,
            prompt=run.prompt,
            tools_used=list(run.tools_used),
            outcome=run.outcome,
            started_at=run.started_at,
        )


@router.post("/ask")
async def ask(
    document_id: str, body: AskRequest, cases: Cases, caller: Caller
) -> AskResponse:
    answer = await cases.agent.ask(
        caller, DocumentId(document_id), instruction=body.instruction
    )
    return AskResponse(answer=answer)


@router.post("/summarize")
async def summarize(document_id: str, cases: Cases, caller: Caller) -> BlocksResponse:
    blocks = await cases.agent.summarize(caller, DocumentId(document_id))
    return BlocksResponse(blocks=blocks)


@router.post("/draft")
async def draft(
    document_id: str, body: AskRequest, cases: Cases, caller: Caller
) -> BlocksResponse:
    blocks = await cases.agent.draft(
        caller, DocumentId(document_id), instruction=body.instruction
    )
    return BlocksResponse(blocks=blocks)


@router.post("/blocks", status_code=201)
async def insert_blocks(
    document_id: str, body: InsertBlocksRequest, cases: Cases, caller: Caller
) -> BlocksResponse:
    """Insert agent-produced blocks into the live document (CRDT peer)."""
    await cases.agent.apply_blocks(caller, DocumentId(document_id), body.blocks)
    return BlocksResponse(blocks=body.blocks, inserted=True)


@router.post("/ingest", status_code=201)
async def ingest(
    document_id: str, file: UploadFile, cases: Cases, caller: Caller
) -> BlocksResponse:
    blocks = await cases.agent.ingest_file_to_document(
        caller,
        DocumentId(document_id),
        filename=file.filename or "upload",
        content=await file.read(),
    )
    return BlocksResponse(blocks=blocks, inserted=bool(blocks))


@router.get("/runs")
async def run_history(
    document_id: str, cases: Cases, caller: Caller
) -> list[AgentRunResponse]:
    runs = await cases.agent.run_history(caller, DocumentId(document_id))
    return [AgentRunResponse.from_domain(r) for r in runs]
