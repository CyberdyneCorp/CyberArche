"""Sharing use cases (permissions-sharing spec): invites, links, comments.

All checks run through AccessControl here, so HTTP, realtime, and MCP
enforce identically — no surface bypasses access control.
"""

from __future__ import annotations

from datetime import datetime

from cyberarche.application.authz import AccessControl
from cyberarche.application.kernel import CallerContext
from cyberarche.application.ports.repositories import (
    DocumentRepository,
    MembershipRepository,
)
from cyberarche.application.ports.sharing import CommentRepository, ShareLinkRepository
from cyberarche.application.ports.telemetry import ClockPort, IdPort
from cyberarche.domain.documents import Document
from cyberarche.domain.errors import NotAuthorized, NotFound
from cyberarche.domain.ids import DocumentId, ShareLinkId, UserId, WorkspaceId
from cyberarche.domain.memberships import (
    DocumentGrant,
    Role,
    WorkspaceMembership,
    role_at_least,
)
from cyberarche.domain.sharing import Comment, ShareLink, SharePermission


class SharingUseCases:
    def __init__(
        self,
        documents: DocumentRepository,
        memberships: MembershipRepository,
        share_links: ShareLinkRepository,
        comments: CommentRepository,
        access: AccessControl,
        clock: ClockPort,
        ids: IdPort,
    ) -> None:
        self._documents = documents
        self._memberships = memberships
        self._share_links = share_links
        self._comments = comments
        self._access = access
        self._clock = clock
        self._ids = ids

    # ---- invites ------------------------------------------------------------

    async def invite_to_workspace(
        self,
        caller: CallerContext,
        workspace_id: WorkspaceId,
        *,
        user_id: UserId,
        role: Role,
    ) -> WorkspaceMembership:
        """Invite a CyberdyneAuth identity to the workspace with a role."""
        await self._access.require_workspace(caller, workspace_id, Role.OWNER)
        membership = WorkspaceMembership(
            workspace_id=workspace_id,
            user_id=user_id,
            role=role,
            granted_at=self._clock.now(),
        )
        await self._memberships.add_workspace_member(membership)
        return membership

    async def grant_on_document(
        self,
        caller: CallerContext,
        document_id: DocumentId,
        *,
        user_id: UserId,
        role: Role,
    ) -> DocumentGrant:
        """Document-level override of the inherited workspace role."""
        document = await self._document(caller, document_id)
        await self._access.require_document(caller, document, Role.OWNER)
        grant = DocumentGrant(
            document_id=document_id,
            user_id=user_id,
            role=role,
            granted_at=self._clock.now(),
        )
        await self._memberships.add_document_grant(grant)
        return grant

    # ---- share links ----------------------------------------------------------

    async def create_share_link(
        self,
        caller: CallerContext,
        document_id: DocumentId,
        *,
        permission: SharePermission,
        expires_at: datetime | None = None,
    ) -> ShareLink:
        document = await self._document(caller, document_id)
        await self._access.require_document(caller, document, Role.OWNER)
        link = ShareLink(
            id=ShareLinkId(self._ids.new_id()),
            document_id=document_id,
            permission=permission,
            created_by=caller.user_id,
            created_at=self._clock.now(),
            expires_at=expires_at,
        )
        await self._share_links.add(link)
        return link

    async def revoke_share_link(
        self, caller: CallerContext, document_id: DocumentId, link_id: ShareLinkId
    ) -> ShareLink:
        document = await self._document(caller, document_id)
        await self._access.require_document(caller, document, Role.OWNER)
        link = await self._share_links.get(link_id)
        if link is None or link.document_id != document_id:
            raise NotFound("share link not found")
        revoked = link.revoke(self._clock.now())
        await self._share_links.update(revoked)
        return revoked

    async def list_share_links(
        self, caller: CallerContext, document_id: DocumentId
    ) -> list[ShareLink]:
        document = await self._document(caller, document_id)
        await self._access.require_document(caller, document, Role.OWNER)
        return await self._share_links.list_for_document(document_id)

    async def open_share_link(
        self, caller: CallerContext, link_id: ShareLinkId
    ) -> Document:
        """Grant the caller the link's permission level on its document.

        A revoked or expired link is denied. Note: the recipient's tenant may
        differ from the document's — share-link access is cross-tenant by
        design, resolved through the grant, never through tenant scoping.
        """
        link = await self._share_links.get(link_id)
        if link is None or not link.is_usable(self._clock.now()):
            raise NotAuthorized("share link is invalid, expired, or revoked")
        await self._memberships.add_document_grant(
            DocumentGrant(
                document_id=link.document_id,
                user_id=caller.user_id,
                role=link.permission.as_role(),
                granted_at=self._clock.now(),
            )
        )
        document = await self._documents.get_any_tenant(link.document_id)
        if document is None or document.trashed:
            raise NotFound("document not found")
        return document

    # ---- comments -------------------------------------------------------------

    async def add_comment(
        self,
        caller: CallerContext,
        document_id: DocumentId,
        *,
        block_id: str,
        body: str,
    ) -> Comment:
        document = await self._document(caller, document_id)
        await self._access.require_document(caller, document, Role.COMMENTER)
        comment = Comment(
            id=self._ids.new_id(),
            document_id=document_id,
            block_id=block_id,
            author_id=caller.user_id,
            body=body,
            created_at=self._clock.now(),
        )
        await self._comments.add(comment)
        return comment

    async def list_comments(
        self, caller: CallerContext, document_id: DocumentId
    ) -> list[Comment]:
        document = await self._document(caller, document_id)
        await self._access.require_document(caller, document, Role.VIEWER)
        return await self._comments.list_for_document(document_id)

    async def resolve_comment(
        self, caller: CallerContext, document_id: DocumentId, comment_id: str
    ) -> Comment:
        """The author or any editor may resolve a comment."""
        document = await self._document(caller, document_id)
        comment = await self._comments.get(document_id, comment_id)
        if comment is None:
            raise NotFound("comment not found")
        if comment.author_id != caller.user_id:
            role = await self._access.document_role(caller, document)
            if role is None or not role_at_least(role, Role.EDITOR):
                raise NotAuthorized("only the author or an editor may resolve")
        else:
            await self._access.require_document(caller, document, Role.COMMENTER)
        resolved = comment.resolve(by=caller.user_id, now=self._clock.now())
        await self._comments.update(resolved)
        return resolved

    async def _document(
        self, caller: CallerContext, document_id: DocumentId
    ) -> Document:
        document = await self._documents.get(caller.tenant_id, document_id)
        if document is None:
            document = await self._documents.get_any_tenant(document_id)
            if document is None or await self._access.document_role(
                caller, document
            ) is None:
                raise NotFound("document not found")
        if document.trashed:
            raise NotFound("document not found")
        return document
