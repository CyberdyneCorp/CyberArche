"""Agent skill endpoints (ai-agent spec): save/list/update/delete named agent
instruction templates and expand one into a runnable instruction string."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from cyberarche.adapters.inbound.http.dependencies import Caller, Cases
from cyberarche.domain.ids import AgentSkillId, WorkspaceId
from cyberarche.domain.skills import AgentSkill

router = APIRouter(tags=["agent-skills"])


class SkillResponse(BaseModel):
    id: str
    name: str
    description: str
    instruction: str
    variables: list[str]
    created_by: str
    created_at: datetime

    @staticmethod
    def from_domain(s: AgentSkill) -> "SkillResponse":
        return SkillResponse(
            id=s.id,
            name=s.name,
            description=s.description,
            instruction=s.instruction,
            variables=s.variables,
            created_by=s.created_by,
            created_at=s.created_at,
        )


class SaveSkillRequest(BaseModel):
    name: str
    instruction: str
    description: str = ""


class InstantiateRequest(BaseModel):
    values: dict[str, str] = {}


class InstructionResponse(BaseModel):
    instruction: str


_BASE = "/api/v1/workspaces/{workspace_id}/agent/skills"


@router.get(_BASE)
async def list_skills(
    workspace_id: str, cases: Cases, caller: Caller
) -> list[SkillResponse]:
    skills = await cases.skills.list(caller, WorkspaceId(workspace_id))
    return [SkillResponse.from_domain(s) for s in skills]


@router.post(_BASE, status_code=201)
async def save_skill(
    workspace_id: str, body: SaveSkillRequest, cases: Cases, caller: Caller
) -> SkillResponse:
    skill = await cases.skills.save(
        caller,
        WorkspaceId(workspace_id),
        name=body.name,
        instruction=body.instruction,
        description=body.description,
    )
    return SkillResponse.from_domain(skill)


@router.put(f"{_BASE}/{{skill_id}}")
async def update_skill(
    workspace_id: str,
    skill_id: str,
    body: SaveSkillRequest,
    cases: Cases,
    caller: Caller,
) -> SkillResponse:
    skill = await cases.skills.update(
        caller,
        WorkspaceId(workspace_id),
        AgentSkillId(skill_id),
        name=body.name,
        instruction=body.instruction,
        description=body.description,
    )
    return SkillResponse.from_domain(skill)


@router.delete(f"{_BASE}/{{skill_id}}", status_code=204)
async def delete_skill(
    workspace_id: str, skill_id: str, cases: Cases, caller: Caller
) -> None:
    await cases.skills.delete(
        caller, WorkspaceId(workspace_id), AgentSkillId(skill_id)
    )


@router.post(f"{_BASE}/{{skill_id}}/instantiate")
async def instantiate_skill(
    workspace_id: str,
    skill_id: str,
    body: InstantiateRequest,
    cases: Cases,
    caller: Caller,
) -> InstructionResponse:
    instruction = await cases.skills.instantiate(
        caller, WorkspaceId(workspace_id), AgentSkillId(skill_id), body.values
    )
    return InstructionResponse(instruction=instruction)
