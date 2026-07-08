"""Sharing endpoints (permissions-sharing spec): invites, links, comments."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from cyberarche.adapters.inbound.http.dependencies import Caller, Cases
from cyberarche.domain.ids import DocumentId, ShareLinkId, UserId, WorkspaceId
from cyberarche.domain.memberships import Role
from cyberarche.domain.sharing import Comment, ShareLink, SharePermission

router = APIRouter(prefix="/api/v1", tags=["sharing"])


class InviteRequest(BaseModel):
    user_id: str
    role: Role


class GrantResponse(BaseModel):
    user_id: str
    role: Role
    granted_at: datetime


class CreateShareLinkRequest(BaseModel):
    permission: SharePermission
    expires_at: datetime | None = None


class ShareLinkResponse(BaseModel):
    id: str
    document_id: str
    permission: SharePermission
    created_at: datetime
    expires_at: datetime | None
    revoked: bool

    @staticmethod
    def from_domain(link: ShareLink) -> "ShareLinkResponse":
        return ShareLinkResponse(
            id=link.id,
            document_id=link.document_id,
            permission=link.permission,
            created_at=link.created_at,
            expires_at=link.expires_at,
            revoked=link.revoked_at is not None,
        )


class CommentRequest(BaseModel):
    block_id: str
    body: str


class CommentResponse(BaseModel):
    id: str
    block_id: str
    author_id: str
    body: str
    created_at: datetime
    resolved: bool

    @staticmethod
    def from_domain(comment: Comment) -> "CommentResponse":
        return CommentResponse(
            id=comment.id,
            block_id=comment.block_id,
            author_id=comment.author_id,
            body=comment.body,
            created_at=comment.created_at,
            resolved=comment.resolved_at is not None,
        )


@router.post("/workspaces/{workspace_id}/invites", status_code=201)
async def invite_to_workspace(
    workspace_id: str, body: InviteRequest, cases: Cases, caller: Caller
) -> GrantResponse:
    membership = await cases.sharing.invite_to_workspace(
        caller, WorkspaceId(workspace_id), user_id=UserId(body.user_id), role=body.role
    )
    return GrantResponse(
        user_id=membership.user_id, role=membership.role, granted_at=membership.granted_at
    )


@router.post("/documents/{document_id}/grants", status_code=201)
async def grant_on_document(
    document_id: str, body: InviteRequest, cases: Cases, caller: Caller
) -> GrantResponse:
    grant = await cases.sharing.grant_on_document(
        caller, DocumentId(document_id), user_id=UserId(body.user_id), role=body.role
    )
    return GrantResponse(
        user_id=grant.user_id, role=grant.role, granted_at=grant.granted_at
    )


@router.post("/documents/{document_id}/share-links", status_code=201)
async def create_share_link(
    document_id: str, body: CreateShareLinkRequest, cases: Cases, caller: Caller
) -> ShareLinkResponse:
    link = await cases.sharing.create_share_link(
        caller,
        DocumentId(document_id),
        permission=body.permission,
        expires_at=body.expires_at,
    )
    return ShareLinkResponse.from_domain(link)


@router.get("/documents/{document_id}/share-links")
async def list_share_links(
    document_id: str, cases: Cases, caller: Caller
) -> list[ShareLinkResponse]:
    links = await cases.sharing.list_share_links(caller, DocumentId(document_id))
    return [ShareLinkResponse.from_domain(l) for l in links]


@router.delete("/documents/{document_id}/share-links/{link_id}")
async def revoke_share_link(
    document_id: str, link_id: str, cases: Cases, caller: Caller
) -> ShareLinkResponse:
    link = await cases.sharing.revoke_share_link(
        caller, DocumentId(document_id), ShareLinkId(link_id)
    )
    return ShareLinkResponse.from_domain(link)


@router.post("/share-links/{link_id}/open")
async def open_share_link(link_id: str, cases: Cases, caller: Caller) -> dict:
    document = await cases.sharing.open_share_link(caller, ShareLinkId(link_id))
    return {"document_id": document.id, "title": document.title}


@router.post("/documents/{document_id}/comments", status_code=201)
async def add_comment(
    document_id: str, body: CommentRequest, cases: Cases, caller: Caller
) -> CommentResponse:
    comment = await cases.sharing.add_comment(
        caller, DocumentId(document_id), block_id=body.block_id, body=body.body
    )
    return CommentResponse.from_domain(comment)


@router.get("/documents/{document_id}/comments")
async def list_comments(
    document_id: str, cases: Cases, caller: Caller
) -> list[CommentResponse]:
    comments = await cases.sharing.list_comments(caller, DocumentId(document_id))
    return [CommentResponse.from_domain(c) for c in comments]


@router.post("/documents/{document_id}/comments/{comment_id}/resolve")
async def resolve_comment(
    document_id: str, comment_id: str, cases: Cases, caller: Caller
) -> CommentResponse:
    comment = await cases.sharing.resolve_comment(
        caller, DocumentId(document_id), comment_id
    )
    return CommentResponse.from_domain(comment)
