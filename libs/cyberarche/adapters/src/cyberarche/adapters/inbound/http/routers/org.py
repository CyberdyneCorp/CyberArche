"""Org directory endpoints (org-directory spec).

The organization always comes from the caller's verified claims — no
request input can select another org.
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel

from cyberarche.adapters.inbound.http.dependencies import Caller, Cases
from cyberarche.application.ports.identity import DirectoryPage

router = APIRouter(prefix="/api/v1/org", tags=["org"])


class OrgUserResponse(BaseModel):
    id: str
    email: str | None
    avatar_url: str | None
    is_active: bool


class OrgUsersResponse(BaseModel):
    users: list[OrgUserResponse]
    total: int
    page: int
    page_size: int

    @staticmethod
    def from_page(result: DirectoryPage) -> "OrgUsersResponse":
        return OrgUsersResponse(
            users=[
                OrgUserResponse(
                    id=user.id,
                    email=user.email,
                    avatar_url=user.avatar_url,
                    is_active=user.is_active,
                )
                for user in result.users
            ],
            total=result.total,
            page=result.page,
            page_size=result.page_size,
        )


@router.get("/users")
async def list_org_users(
    cases: Cases,
    caller: Caller,
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> OrgUsersResponse:
    result = await cases.org_directory.list_org_users(
        caller, search=search, page=page, page_size=page_size
    )
    return OrgUsersResponse.from_page(result)
