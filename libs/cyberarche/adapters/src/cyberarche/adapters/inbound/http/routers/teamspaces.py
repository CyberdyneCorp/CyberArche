"""Teamspace and favourite endpoints (teamspaces / favorites specs)."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from cyberarche.adapters.inbound.http.dependencies import Caller, Cases
from cyberarche.adapters.inbound.http.schemas import DocumentResponse
from cyberarche.domain.ids import DocumentId, TeamspaceId, UserId, WorkspaceId
from cyberarche.domain.memberships import Role
from cyberarche.domain.teamspaces import Teamspace, TeamspaceMembership

router = APIRouter(tags=["teamspaces"])


class CreateTeamspaceRequest(BaseModel):
    name: str
    icon: str = "T"


class TeamspaceResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    icon: str
    created_at: datetime

    @staticmethod
    def from_domain(teamspace: Teamspace) -> "TeamspaceResponse":
        return TeamspaceResponse(
            id=teamspace.id,
            workspace_id=teamspace.workspace_id,
            name=teamspace.name,
            icon=teamspace.icon,
            created_at=teamspace.created_at,
        )


class AddMemberRequest(BaseModel):
    user_id: str
    role: Role


class MemberResponse(BaseModel):
    user_id: str
    role: Role
    granted_at: datetime

    @staticmethod
    def from_domain(m: TeamspaceMembership) -> "MemberResponse":
        return MemberResponse(user_id=m.user_id, role=m.role, granted_at=m.granted_at)


@router.post("/api/v1/workspaces/{workspace_id}/teamspaces", status_code=201)
async def create_teamspace(
    workspace_id: str, body: CreateTeamspaceRequest, cases: Cases, caller: Caller
) -> TeamspaceResponse:
    teamspace = await cases.teamspaces.create(
        caller, WorkspaceId(workspace_id), name=body.name, icon=body.icon
    )
    return TeamspaceResponse.from_domain(teamspace)


@router.get("/api/v1/workspaces/{workspace_id}/teamspaces")
async def list_teamspaces(
    workspace_id: str, cases: Cases, caller: Caller
) -> list[TeamspaceResponse]:
    teamspaces = await cases.teamspaces.list(caller, WorkspaceId(workspace_id))
    return [TeamspaceResponse.from_domain(t) for t in teamspaces]


@router.get("/api/v1/teamspaces/{teamspace_id}/documents")
async def teamspace_documents(
    teamspace_id: str, cases: Cases, caller: Caller
) -> list[DocumentResponse]:
    documents = await cases.teamspaces.documents(caller, TeamspaceId(teamspace_id))
    return [DocumentResponse.from_domain(d) for d in documents]


@router.get("/api/v1/teamspaces/{teamspace_id}/members")
async def teamspace_members(
    teamspace_id: str, cases: Cases, caller: Caller
) -> list[MemberResponse]:
    members = await cases.teamspaces.members(caller, TeamspaceId(teamspace_id))
    return [MemberResponse.from_domain(m) for m in members]


@router.post("/api/v1/teamspaces/{teamspace_id}/members", status_code=201)
async def add_teamspace_member(
    teamspace_id: str, body: AddMemberRequest, cases: Cases, caller: Caller
) -> MemberResponse:
    membership = await cases.teamspaces.add_member(
        caller, TeamspaceId(teamspace_id), user_id=UserId(body.user_id), role=body.role
    )
    return MemberResponse.from_domain(membership)


@router.delete("/api/v1/teamspaces/{teamspace_id}/members/{user_id}", status_code=204)
async def remove_teamspace_member(
    teamspace_id: str, user_id: str, cases: Cases, caller: Caller
) -> None:
    await cases.teamspaces.remove_member(
        caller, TeamspaceId(teamspace_id), UserId(user_id)
    )


@router.delete("/api/v1/teamspaces/{teamspace_id}", status_code=204)
async def delete_teamspace(
    teamspace_id: str, cases: Cases, caller: Caller
) -> None:
    await cases.teamspaces.delete(caller, TeamspaceId(teamspace_id))


# ---- favourites -------------------------------------------------------------


class FavoriteRequest(BaseModel):
    document_id: str


@router.get("/api/v1/favorites")
async def list_favorites(cases: Cases, caller: Caller) -> list[DocumentResponse]:
    documents = await cases.favorites.list(caller)
    return [DocumentResponse.from_domain(d) for d in documents]


@router.post("/api/v1/favorites", status_code=204)
async def add_favorite(body: FavoriteRequest, cases: Cases, caller: Caller) -> None:
    await cases.favorites.add(caller, DocumentId(body.document_id))


@router.delete("/api/v1/favorites/{document_id}", status_code=204)
async def remove_favorite(document_id: str, cases: Cases, caller: Caller) -> None:
    await cases.favorites.remove(caller, DocumentId(document_id))
