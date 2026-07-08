"""Teamspace aggregate (teamspaces spec).

A teamspace is a named, member-scoped grouping of documents inside one
workspace. Membership grants access to its documents in addition to any
workspace role (see AccessControl).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from cyberarche.domain.errors import ValidationFailed
from cyberarche.domain.ids import TeamspaceId, TenantId, UserId, WorkspaceId
from cyberarche.domain.memberships import Role

MAX_NAME_LENGTH = 120


@dataclass(frozen=True, slots=True)
class Teamspace:
    id: TeamspaceId
    workspace_id: WorkspaceId
    tenant_id: TenantId
    name: str
    icon: str
    created_by: UserId
    created_at: datetime

    @staticmethod
    def create(
        *,
        id: TeamspaceId,
        workspace_id: WorkspaceId,
        tenant_id: TenantId,
        name: str,
        icon: str = "T",
        created_by: UserId,
        created_at: datetime,
    ) -> "Teamspace":
        return Teamspace(
            id=id,
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            name=_valid_name(name),
            icon=icon or "T",
            created_by=created_by,
            created_at=created_at,
        )

    def rename(self, name: str) -> "Teamspace":
        return replace(self, name=_valid_name(name))


@dataclass(frozen=True, slots=True)
class TeamspaceMembership:
    teamspace_id: TeamspaceId
    user_id: UserId
    role: Role
    granted_at: datetime


def _valid_name(name: str) -> str:
    name = name.strip()
    if not name:
        raise ValidationFailed("teamspace name must not be empty")
    if len(name) > MAX_NAME_LENGTH:
        raise ValidationFailed(f"teamspace name exceeds {MAX_NAME_LENGTH} characters")
    return name
