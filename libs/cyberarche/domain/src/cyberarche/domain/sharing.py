"""Share links and comments (permissions-sharing spec)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from cyberarche.domain.ids import DocumentId, ShareLinkId, UserId
from cyberarche.domain.memberships import Role


class SharePermission(StrEnum):
    VIEW = "view"
    COMMENT = "comment"
    EDIT = "edit"

    def as_role(self) -> Role:
        return {
            SharePermission.VIEW: Role.VIEWER,
            SharePermission.COMMENT: Role.COMMENTER,
            SharePermission.EDIT: Role.EDITOR,
        }[self]


@dataclass(frozen=True, slots=True)
class ShareLink:
    id: ShareLinkId
    document_id: DocumentId
    permission: SharePermission
    created_by: UserId
    created_at: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None

    def is_usable(self, now: datetime) -> bool:
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None and now >= self.expires_at:
            return False
        return True

    def revoke(self, now: datetime) -> "ShareLink":
        return replace(self, revoked_at=now)


@dataclass(frozen=True, slots=True)
class Comment:
    id: str
    document_id: DocumentId
    block_id: str
    author_id: UserId
    body: str
    created_at: datetime
    resolved_at: datetime | None = None
    resolved_by: UserId | None = None

    def resolve(self, *, by: UserId, now: datetime) -> "Comment":
        return replace(self, resolved_at=now, resolved_by=by)
