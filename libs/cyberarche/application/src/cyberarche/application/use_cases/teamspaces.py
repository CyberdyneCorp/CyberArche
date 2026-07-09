"""Teamspace and favourite use cases (teamspaces / favorites specs)."""

from __future__ import annotations

from dataclasses import replace

from cyberarche.application.authz import AccessControl
from cyberarche.application.kernel import CallerContext
from cyberarche.application.ports.folders import FolderRepository
from cyberarche.application.ports.repositories import DocumentRepository
from cyberarche.application.ports.teamspaces import (
    FavoriteRepository,
    TeamspaceRepository,
)
from cyberarche.application.ports.telemetry import ClockPort, IdPort
from cyberarche.domain.documents import Document
from cyberarche.domain.errors import NotFound
from cyberarche.domain.ids import DocumentId, TeamspaceId, UserId, WorkspaceId
from cyberarche.domain.memberships import Role
from cyberarche.domain.teamspaces import Teamspace, TeamspaceMembership


class TeamspaceUseCases:
    def __init__(
        self,
        teamspaces: TeamspaceRepository,
        documents: DocumentRepository,
        folders: FolderRepository,
        access: AccessControl,
        clock: ClockPort,
        ids: IdPort,
    ) -> None:
        self._teamspaces = teamspaces
        self._documents = documents
        self._folders = folders
        self._access = access
        self._clock = clock
        self._ids = ids

    async def create(
        self,
        caller: CallerContext,
        workspace_id: WorkspaceId,
        *,
        name: str,
        icon: str = "T",
    ) -> Teamspace:
        """Create a teamspace; the creator becomes its owner."""
        await self._access.require_workspace(caller, workspace_id, Role.EDITOR)
        now = self._clock.now()
        teamspace = Teamspace.create(
            id=TeamspaceId(self._ids.new_id()),
            workspace_id=workspace_id,
            tenant_id=caller.tenant_id,
            name=name,
            icon=icon,
            created_by=caller.user_id,
            created_at=now,
        )
        await self._teamspaces.add(teamspace)
        await self._teamspaces.add_member(
            TeamspaceMembership(
                teamspace_id=teamspace.id,
                user_id=caller.user_id,
                role=Role.OWNER,
                granted_at=now,
            )
        )
        return teamspace

    async def list(
        self, caller: CallerContext, workspace_id: WorkspaceId
    ) -> list[Teamspace]:
        """Teamspaces of the workspace the caller may see: all of them for a
        workspace member, otherwise only those they belong to."""
        workspace_role = await self._access.workspace_role(caller, workspace_id)
        if workspace_role is not None:
            return await self._teamspaces.list_for_workspace(
                caller.tenant_id, workspace_id
            )
        return await self._teamspaces.teamspaces_for_user(
            caller.tenant_id, workspace_id, caller.user_id
        )

    async def get(
        self, caller: CallerContext, teamspace_id: TeamspaceId
    ) -> Teamspace:
        teamspace = await self._teamspaces.get(caller.tenant_id, teamspace_id)
        if teamspace is None:
            raise NotFound("teamspace not found")
        await self._access.require_teamspace(caller, teamspace, Role.VIEWER)
        return teamspace

    async def add_member(
        self,
        caller: CallerContext,
        teamspace_id: TeamspaceId,
        *,
        user_id: UserId,
        role: Role,
    ) -> TeamspaceMembership:
        teamspace = await self._require(caller, teamspace_id, Role.OWNER)
        membership = TeamspaceMembership(
            teamspace_id=teamspace.id,
            user_id=user_id,
            role=role,
            granted_at=self._clock.now(),
        )
        await self._teamspaces.add_member(membership)
        return membership

    async def remove_member(
        self, caller: CallerContext, teamspace_id: TeamspaceId, user_id: UserId
    ) -> None:
        await self._require(caller, teamspace_id, Role.OWNER)
        await self._teamspaces.remove_member(teamspace_id, user_id)

    async def members(
        self, caller: CallerContext, teamspace_id: TeamspaceId
    ) -> list[TeamspaceMembership]:
        await self._require(caller, teamspace_id, Role.VIEWER)
        return await self._teamspaces.members(teamspace_id)

    async def delete(self, caller: CallerContext, teamspace_id: TeamspaceId) -> None:
        """Delete a teamspace (owner only): move its documents — including those
        under its folders — to trash, remove its folders, then remove it."""
        await self._require(caller, teamspace_id, Role.OWNER)
        now = self._clock.now()
        docs = await self._documents.list_for_teamspace(caller.tenant_id, teamspace_id)
        if docs:
            # Trash and detach, so the docs survive in the caller's trash and hold
            # no dangling teamspace/folder reference once the teamspace is gone.
            await self._documents.update_many(
                [
                    replace(
                        doc,
                        trashed=True,
                        teamspace_id=None,
                        folder_id=None,
                        updated_at=now,
                    )
                    for doc in docs
                ]
            )
        for folder in await self._folders.list_for_teamspace(
            caller.tenant_id, teamspace_id
        ):
            await self._folders.delete(caller.tenant_id, folder.id)
        await self._teamspaces.delete(caller.tenant_id, teamspace_id)

    async def documents(
        self, caller: CallerContext, teamspace_id: TeamspaceId
    ) -> list[Document]:
        teamspace = await self._require(caller, teamspace_id, Role.VIEWER)
        return await self._documents.list_for_teamspace(
            caller.tenant_id, teamspace.id
        )

    async def _require(
        self, caller: CallerContext, teamspace_id: TeamspaceId, role: Role
    ) -> Teamspace:
        teamspace = await self._teamspaces.get(caller.tenant_id, teamspace_id)
        if teamspace is None:
            raise NotFound("teamspace not found")
        await self._access.require_teamspace(caller, teamspace, role)
        return teamspace


class FavoriteUseCases:
    def __init__(
        self,
        favorites: FavoriteRepository,
        documents: DocumentRepository,
        access: AccessControl,
    ) -> None:
        self._favorites = favorites
        self._documents = documents
        self._access = access

    async def add(self, caller: CallerContext, document_id: DocumentId) -> None:
        await self._viewable(caller, document_id)
        await self._favorites.add(caller.user_id, document_id)

    async def remove(self, caller: CallerContext, document_id: DocumentId) -> None:
        await self._favorites.remove(caller.user_id, document_id)

    async def list(self, caller: CallerContext) -> list[Document]:
        """Only this user's favourites, and only ones still visible to them."""
        documents: list[Document] = []
        for document_id in await self._favorites.list_for_user(caller.user_id):
            document = await self._documents.get(caller.tenant_id, document_id)
            if document is None or document.trashed:
                continue
            if await self._access.document_role(caller, document) is not None:
                documents.append(document)
        return documents

    async def _viewable(self, caller: CallerContext, document_id: DocumentId) -> Document:
        document = await self._documents.get(caller.tenant_id, document_id)
        if document is None or document.trashed:
            raise NotFound("document not found")
        await self._access.require_document(caller, document, Role.VIEWER)
        return document
