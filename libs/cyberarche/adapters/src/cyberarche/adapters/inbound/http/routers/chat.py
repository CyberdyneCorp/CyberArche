"""Workspace-wide chat endpoint (ai-agent spec): "Chat with your workspace".

Read-only, workspace-scoped Q&A grounded in the workspace's documents. Thin:
parse -> delegate to the use case -> DTO.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from cyberarche.adapters.inbound.http.dependencies import Caller, Cases
from cyberarche.domain.ids import WorkspaceId

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}/chat", tags=["chat"])


class ChatHistoryTurn(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    instruction: str
    # Recent conversation turns so follow-ups keep context.
    history: list[ChatHistoryTurn] | None = None


class ChatSourceResponse(BaseModel):
    id: str
    title: str


class ChatResponse(BaseModel):
    answer: str
    # The source documents the answer drew on (clickable in the UI).
    sources: list[ChatSourceResponse]


@router.post("")
async def chat(
    workspace_id: str, body: ChatRequest, cases: Cases, caller: Caller
) -> ChatResponse:
    answer = await cases.workspace_chat.ask(
        caller,
        WorkspaceId(workspace_id),
        instruction=body.instruction,
        history=[(h.role, h.content) for h in (body.history or [])],
    )
    return ChatResponse(
        answer=answer.text,
        sources=[
            ChatSourceResponse(id=source.id, title=source.title)
            for source in answer.sources
        ],
    )
