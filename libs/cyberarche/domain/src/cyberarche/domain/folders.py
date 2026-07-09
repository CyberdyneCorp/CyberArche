"""Folder aggregate (folders spec).

A folder groups documents and sub-folders inside a workspace. It lives in a
teamspace (shared with the teamspace's members) or in the private space
(teamspace_id is None -> visible only to its creator). Folders may nest.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from cyberarche.domain.errors import ValidationFailed
from cyberarche.domain.ids import (
    FolderId,
    TeamspaceId,
    TenantId,
    UserId,
    WorkspaceId,
)

MAX_NAME_LENGTH = 120


def _valid_name(name: str) -> str:
    name = name.strip()
    if not name:
        raise ValidationFailed("folder name must not be empty")
    if len(name) > MAX_NAME_LENGTH:
        raise ValidationFailed(f"folder name exceeds {MAX_NAME_LENGTH} characters")
    return name


@dataclass(frozen=True, slots=True)
class Folder:
    id: FolderId
    workspace_id: WorkspaceId
    tenant_id: TenantId
    name: str
    created_by: UserId
    created_at: datetime
    # None => private folder (creator-only). Otherwise the owning teamspace.
    teamspace_id: TeamspaceId | None = None
    # None => a top-level folder in its teamspace/private space.
    parent_folder_id: FolderId | None = None

    @staticmethod
    def create(
        *,
        id: FolderId,
        workspace_id: WorkspaceId,
        tenant_id: TenantId,
        name: str,
        created_by: UserId,
        created_at: datetime,
        teamspace_id: TeamspaceId | None = None,
        parent_folder_id: FolderId | None = None,
    ) -> "Folder":
        return Folder(
            id=id,
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            name=_valid_name(name),
            created_by=created_by,
            created_at=created_at,
            teamspace_id=teamspace_id,
            parent_folder_id=parent_folder_id,
        )

    @property
    def is_private(self) -> bool:
        return self.teamspace_id is None

    def rename(self, name: str) -> "Folder":
        return replace(self, name=_valid_name(name))
