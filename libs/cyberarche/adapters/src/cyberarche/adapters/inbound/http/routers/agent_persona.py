"""Agent persona endpoints (ai-agent spec): a workspace's custom instructions
(shared + personal layers) and its durable agent memories."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from cyberarche.adapters.inbound.http.dependencies import Caller, Cases
from cyberarche.domain.agent_persona import AgentMemory
from cyberarche.domain.ids import AgentMemoryId, WorkspaceId

router = APIRouter(tags=["agent-persona"])


class InstructionsResponse(BaseModel):
    workspace: str | None
    personal: str | None


class SetInstructionsRequest(BaseModel):
    scope: str  # "workspace" | "personal"
    text: str


class MemoryResponse(BaseModel):
    id: str
    text: str
    created_by: str
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def from_domain(m: AgentMemory) -> "MemoryResponse":
        return MemoryResponse(
            id=m.id,
            text=m.text,
            created_by=m.created_by,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )


class MemoryRequest(BaseModel):
    text: str


_BASE = "/api/v1/workspaces/{workspace_id}/agent"


@router.get(f"{_BASE}/instructions")
async def get_instructions(
    workspace_id: str, cases: Cases, caller: Caller
) -> InstructionsResponse:
    ws = WorkspaceId(workspace_id)
    return InstructionsResponse(
        workspace=await cases.persona.get_workspace_instructions(caller, ws),
        personal=await cases.persona.get_personal_instructions(caller, ws),
    )


@router.put(f"{_BASE}/instructions", status_code=204)
async def set_instructions(
    workspace_id: str, body: SetInstructionsRequest, cases: Cases, caller: Caller
) -> None:
    ws = WorkspaceId(workspace_id)
    if body.scope == "personal":
        await cases.persona.set_personal_instructions(caller, ws, body.text)
    else:
        await cases.persona.set_workspace_instructions(caller, ws, body.text)


@router.delete(f"{_BASE}/instructions", status_code=204)
async def clear_instructions(
    workspace_id: str, cases: Cases, caller: Caller, scope: str = "workspace"
) -> None:
    ws = WorkspaceId(workspace_id)
    if scope == "personal":
        await cases.persona.clear_personal_instructions(caller, ws)
    else:
        await cases.persona.clear_workspace_instructions(caller, ws)


@router.get(f"{_BASE}/memories")
async def list_memories(
    workspace_id: str, cases: Cases, caller: Caller
) -> list[MemoryResponse]:
    memories = await cases.persona.list_memories(caller, WorkspaceId(workspace_id))
    return [MemoryResponse.from_domain(m) for m in memories]


@router.post(f"{_BASE}/memories", status_code=201)
async def add_memory(
    workspace_id: str, body: MemoryRequest, cases: Cases, caller: Caller
) -> MemoryResponse:
    memory = await cases.persona.add_memory(
        caller, WorkspaceId(workspace_id), body.text
    )
    return MemoryResponse.from_domain(memory)


@router.patch(f"{_BASE}/memories/{{memory_id}}")
async def update_memory(
    workspace_id: str,
    memory_id: str,
    body: MemoryRequest,
    cases: Cases,
    caller: Caller,
) -> MemoryResponse:
    memory = await cases.persona.update_memory(
        caller, WorkspaceId(workspace_id), AgentMemoryId(memory_id), body.text
    )
    return MemoryResponse.from_domain(memory)


@router.delete(f"{_BASE}/memories/{{memory_id}}", status_code=204)
async def delete_memory(
    workspace_id: str, memory_id: str, cases: Cases, caller: Caller
) -> None:
    await cases.persona.delete_memory(
        caller, WorkspaceId(workspace_id), AgentMemoryId(memory_id)
    )
