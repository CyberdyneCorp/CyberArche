from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from cyberarche.adapters.inbound.http.dependencies import Caller, Cases
from cyberarche.adapters.inbound.http.schemas import (
    CreateWorkspaceRequest,
    WorkspaceResponse,
)
from cyberarche.application.use_cases.members import WorkspaceMember
from cyberarche.domain.ids import UserId, WorkspaceId
from cyberarche.domain.memberships import Role, WorkspaceMembership

router = APIRouter(prefix="/api/v1/workspaces", tags=["workspaces"])


class WorkspaceMemberResponse(BaseModel):
    user_id: str
    role: Role
    granted_at: datetime
    email: str | None = None
    avatar_url: str | None = None

    @staticmethod
    def from_member(member: WorkspaceMember) -> "WorkspaceMemberResponse":
        response = WorkspaceMemberResponse.from_membership(member.membership)
        response.email = member.email
        response.avatar_url = member.avatar_url
        return response

    @staticmethod
    def from_membership(m: WorkspaceMembership) -> "WorkspaceMemberResponse":
        return WorkspaceMemberResponse(
            user_id=m.user_id, role=m.role, granted_at=m.granted_at
        )


class UpdateMemberRequest(BaseModel):
    role: Role


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


@router.get("/{workspace_id}/members")
async def list_members(
    workspace_id: str, cases: Cases, caller: Caller
) -> list[WorkspaceMemberResponse]:
    members = await cases.members.list_members(caller, WorkspaceId(workspace_id))
    return [WorkspaceMemberResponse.from_member(m) for m in members]


@router.patch("/{workspace_id}/members/{user_id}")
async def update_member_role(
    workspace_id: str,
    user_id: str,
    body: UpdateMemberRequest,
    cases: Cases,
    caller: Caller,
) -> WorkspaceMemberResponse:
    membership = await cases.members.set_member_role(
        caller, WorkspaceId(workspace_id), user_id=UserId(user_id), role=body.role
    )
    return WorkspaceMemberResponse.from_membership(membership)


@router.delete("/{workspace_id}/members/{user_id}", status_code=204)
async def remove_member(
    workspace_id: str, user_id: str, cases: Cases, caller: Caller
) -> None:
    await cases.members.remove_member(
        caller, WorkspaceId(workspace_id), UserId(user_id)
    )
