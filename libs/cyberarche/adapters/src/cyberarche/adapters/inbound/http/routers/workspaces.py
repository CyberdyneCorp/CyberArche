from __future__ import annotations

from fastapi import APIRouter

from cyberarche.adapters.inbound.http.dependencies import Caller, Cases
from cyberarche.adapters.inbound.http.schemas import (
    CreateWorkspaceRequest,
    WorkspaceResponse,
)
from cyberarche.domain.ids import WorkspaceId

router = APIRouter(prefix="/api/v1/workspaces", tags=["workspaces"])


@router.post("", status_code=201)
async def create_workspace(
    body: CreateWorkspaceRequest, cases: Cases, caller: Caller
) -> WorkspaceResponse:
    workspace = await cases.workspaces.create(caller, name=body.name)
    return WorkspaceResponse.from_domain(workspace)


@router.get("")
async def list_workspaces(cases: Cases, caller: Caller) -> list[WorkspaceResponse]:
    workspaces = await cases.workspaces.list(caller)
    return [WorkspaceResponse.from_domain(w) for w in workspaces]


@router.get("/{workspace_id}")
async def get_workspace(
    workspace_id: str, cases: Cases, caller: Caller
) -> WorkspaceResponse:
    workspace = await cases.workspaces.get(caller, WorkspaceId(workspace_id))
    return WorkspaceResponse.from_domain(workspace)
