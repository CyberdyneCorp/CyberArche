"""Agent endpoints (ai-agent spec): ask, summarize, draft, ingest, history."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, UploadFile
from pydantic import BaseModel

from cyberarche.adapters.inbound.http.dependencies import (
    AccessToken,
    Caller,
    Cases,
)
from cyberarche.application.ports.agent import AgentRun
from cyberarche.domain.ids import DocumentId

router = APIRouter(prefix="/api/v1/documents/{document_id}/agent", tags=["agent"])


class HistoryTurn(BaseModel):
    role: str  # "user" | "agent"
    content: str


class AskRequest(BaseModel):
    instruction: str
    # Optional per-session opt-in: restrict external MCP tools to these
    # connector ids. Omit for no restriction (all enabled connectors).
    enabled_connectors: list[str] | None = None
    # Recent conversation turns so follow-ups ('insert the plot') have context.
    history: list[HistoryTurn] | None = None


class ToolCallResponse(BaseModel):
    name: str
    kind: str  # "mcp" | "editing" | "builtin"
    connector: str | None = None
    arguments: dict
    result: str
    ok: bool


class AskResponse(BaseModel):
    answer: str
    # Insertable representation of the answer (ai-agent spec: every answer
    # can be inserted into the document without retyping it).
    blocks: list[dict]
    # The tool calls the agent made this turn, so the chat can show and expand
    # them (name, arguments, result) — built-in, editing, and external MCP.
    tool_calls: list[ToolCallResponse] = []


class BlocksResponse(BaseModel):
    blocks: list[dict]
    inserted: bool = False


class SummarizeRequest(BaseModel):
    # Optional: summarize only these blocks. Omit for the whole document.
    block_ids: list[str] | None = None


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
    document_id: str,
    body: AskRequest,
    cases: Cases,
    caller: Caller,
    access_token: AccessToken,
) -> AskResponse:
    answer = await cases.agent.ask(
        caller,
        DocumentId(document_id),
        instruction=body.instruction,
        session_connectors=set(body.enabled_connectors)
        if body.enabled_connectors is not None
        else None,
        history=[(h.role, h.content) for h in (body.history or [])],
        access_token=access_token,
    )
    return AskResponse(
        answer=answer.text,
        blocks=answer.blocks,
        tool_calls=[
            ToolCallResponse(
                name=c.name,
                kind=c.kind,
                connector=c.connector,
                arguments=c.arguments,
                result=c.result,
                ok=c.ok,
            )
            for c in answer.tool_calls
        ],
    )


@router.post("/summarize")
async def summarize(
    document_id: str,
    cases: Cases,
    caller: Caller,
    body: SummarizeRequest | None = None,
) -> BlocksResponse:
    blocks = await cases.agent.summarize(
        caller,
        DocumentId(document_id),
        block_ids=body.block_ids if body else None,
    )
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


class ReplaceBlockRequest(BaseModel):
    text: str


@router.patch("/blocks/{block_id}")
async def replace_block_text(
    document_id: str,
    block_id: str,
    body: ReplaceBlockRequest,
    cases: Cases,
    caller: Caller,
) -> dict:
    """Replace a block's text (agent 'Replace selection'), applied through
    the CRDT so collaborators see it live."""
    await cases.agent.update_block(
        caller, DocumentId(document_id), block_id, {"text": body.text}
    )
    return {"block_id": block_id}


@router.delete("/blocks/{block_id}", status_code=204)
async def delete_block(
    document_id: str, block_id: str, cases: Cases, caller: Caller
) -> None:
    await cases.agent.delete_block(caller, DocumentId(document_id), block_id)


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
