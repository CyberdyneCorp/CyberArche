"""Teamspace and favourite repository ports."""

from __future__ import annotations

from typing import Protocol

from cyberarche.domain.ids import (
    DocumentId,
    TeamspaceId,
    TenantId,
    UserId,
    WorkspaceId,
)
from cyberarche.domain.teamspaces import Teamspace, TeamspaceMembership


class TeamspaceRepository(Protocol):
    async def add(self, teamspace: Teamspace) -> None: ...

    async def get(
        self, tenant_id: TenantId, teamspace_id: TeamspaceId
    ) -> Teamspace | None: ...

    async def list_for_workspace(
        self, tenant_id: TenantId, workspace_id: WorkspaceId
    ) -> list[Teamspace]: ...

    async def add_member(self, membership: TeamspaceMembership) -> None: ...

    async def remove_member(self, teamspace_id: TeamspaceId, user_id: UserId) -> None: ...

    async def member_role(
        self, teamspace_id: TeamspaceId, user_id: UserId
    ) -> TeamspaceMembership | None: ...

    async def members(self, teamspace_id: TeamspaceId) -> list[TeamspaceMembership]: ...

    async def teamspaces_for_user(
        self, tenant_id: TenantId, workspace_id: WorkspaceId, user_id: UserId
    ) -> list[Teamspace]: ...

    async def delete(self, tenant_id: TenantId, teamspace_id: TeamspaceId) -> None:
        """Remove the teamspace and its memberships. Documents and folders are
        handled by the use case (documents move to trash, folders are removed)."""
        ...


class FavoriteRepository(Protocol):
    async def add(self, user_id: UserId, document_id: DocumentId) -> None: ...

    async def remove(self, user_id: UserId, document_id: DocumentId) -> None: ...

    async def list_for_user(self, user_id: UserId) -> list[DocumentId]: ...

    async def is_favorite(self, user_id: UserId, document_id: DocumentId) -> bool: ...
