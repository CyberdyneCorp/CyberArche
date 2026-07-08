"""Roles and memberships (permissions-sharing spec).

A document inherits access from its workspace unless a document-level
grant overrides it (the more specific grant wins).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from cyberarche.domain.ids import DocumentId, UserId, WorkspaceId


class Role(StrEnum):
    OWNER = "owner"
    EDITOR = "editor"
    COMMENTER = "commenter"
    VIEWER = "viewer"


# Capability ranking used for "at least" checks.
_ROLE_RANK: dict[Role, int] = {
    Role.VIEWER: 1,
    Role.COMMENTER: 2,
    Role.EDITOR: 3,
    Role.OWNER: 4,
}


def role_at_least(role: Role, required: Role) -> bool:
    return _ROLE_RANK[role] >= _ROLE_RANK[required]


@dataclass(frozen=True, slots=True)
class WorkspaceMembership:
    workspace_id: WorkspaceId
    user_id: UserId
    role: Role
    granted_at: datetime


@dataclass(frozen=True, slots=True)
class DocumentGrant:
    """Document-level override of the workspace role."""

    document_id: DocumentId
    user_id: UserId
    role: Role
    granted_at: datetime


def strongest(*roles: Role | None) -> Role | None:
    """The most capable of the given roles, ignoring absent ones."""
    present = [role for role in roles if role is not None]
    return max(present, key=lambda role: _ROLE_RANK[role]) if present else None


def effective_role(
    workspace_role: Role | None,
    document_grant: Role | None,
    teamspace_role: Role | None = None,
) -> Role | None:
    """A document-level grant overrides everything (it may deliberately
    demote); otherwise the user gets the strongest of their inherited roles:
    workspace membership or membership of the document's teamspace."""
    if document_grant is not None:
        return document_grant
    return strongest(workspace_role, teamspace_role)
