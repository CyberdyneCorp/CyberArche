"""Folder use cases (folders spec): create/list/rename/delete folders that group
documents in a teamspace or the private space."""

from __future__ import annotations

from cyberarche.application.authz import AccessControl
from cyberarche.application.kernel import CallerContext
from cyberarche.application.ports.folders import FolderRepository
from cyberarche.application.ports.repositories import DocumentRepository
from cyberarche.application.ports.telemetry import ClockPort, IdPort
from cyberarche.domain.errors import NotAuthorized, NotFound, ValidationFailed
from cyberarche.domain.folders import Folder
from cyberarche.domain.ids import FolderId, TeamspaceId, WorkspaceId
from cyberarche.domain.memberships import Role, role_at_least, strongest


class FolderUseCases:
    def __init__(
        self,
        folders: FolderRepository,
        documents: DocumentRepository,
        access: AccessControl,
        clock: ClockPort,
        ids: IdPort,
    ) -> None:
        self._folders = folders
        self._documents = documents
        self._access = access
        self._clock = clock
        self._ids = ids

    async def create(
        self,
        caller: CallerContext,
        workspace_id: WorkspaceId,
        *,
        name: str,
        teamspace_id: TeamspaceId | None = None,
        parent_folder_id: FolderId | None = None,
    ) -> Folder:
        """Create a folder in a teamspace (needs editor there) or in the caller's
        private space (needs workspace membership)."""
        if teamspace_id is not None:
            if not await self._can_edit_teamspace(caller, workspace_id, teamspace_id):
                raise NotAuthorized("requires editor on the teamspace")
        else:
            await self._access.require_workspace(caller, workspace_id, Role.VIEWER)
        if parent_folder_id is not None:
            parent = await self._require(caller, parent_folder_id)
            # A nested folder inherits its parent's scope.
            teamspace_id = parent.teamspace_id
        folder = Folder.create(
            id=FolderId(self._ids.new_id()),
            workspace_id=workspace_id,
            tenant_id=caller.tenant_id,
            name=name,
            created_by=caller.user_id,
            created_at=self._clock.now(),
            teamspace_id=teamspace_id,
            parent_folder_id=parent_folder_id,
        )
        await self._folders.add(folder)
        return folder

    async def list_for_workspace(
        self, caller: CallerContext, workspace_id: WorkspaceId
    ) -> list[Folder]:
        """Folders the caller can see: teamspace folders they can access, plus
        their own private folders."""
        folders = await self._folders.list_for_workspace(
            caller.tenant_id, workspace_id
        )
        visible: list[Folder] = []
        for folder in folders:
            if await self._can_see(caller, folder):
                visible.append(folder)
        return visible

    async def rename(
        self, caller: CallerContext, folder_id: FolderId, *, name: str
    ) -> Folder:
        folder = await self._require(caller, folder_id, edit=True)
        renamed = folder.rename(name)
        await self._folders.update(renamed)
        return renamed

    async def delete(self, caller: CallerContext, folder_id: FolderId) -> None:
        await self._require(caller, folder_id, edit=True)
        # Detach documents in the folder and its sub-folders so deleting a
        # container never destroys documents (D-4). Postgres' ON DELETE SET NULL
        # would also do this; doing it here keeps the in-memory adapter in step.
        for fid in await self._subtree_ids(caller, folder_id):
            for doc in await self._documents.list_for_folder(caller.tenant_id, fid):
                from dataclasses import replace

                await self._documents.update(
                    replace(doc, folder_id=None, updated_at=self._clock.now())
                )
        await self._folders.delete(caller.tenant_id, folder_id)

    async def children(
        self, caller: CallerContext, folder_id: FolderId
    ) -> list[Folder]:
        """Sub-folders of a folder the caller can see."""
        await self._require(caller, folder_id)
        folders = await self._folders.list_for_workspace(
            caller.tenant_id, (await self._require(caller, folder_id)).workspace_id
        )
        return [f for f in folders if f.parent_folder_id == folder_id]

    async def _subtree_ids(
        self, caller: CallerContext, folder_id: FolderId
    ) -> list[FolderId]:
        root = await self._folders.get(caller.tenant_id, folder_id)
        if root is None:
            return []
        all_folders = await self._folders.list_for_workspace(
            caller.tenant_id, root.workspace_id
        )
        ids = [folder_id]
        frontier = [folder_id]
        while frontier:
            current = frontier.pop()
            for f in all_folders:
                if f.parent_folder_id == current and f.id not in ids:
                    ids.append(f.id)
                    frontier.append(f.id)
        return ids

    # ---- helpers -----------------------------------------------------------

    async def _can_edit_teamspace(
        self, caller: CallerContext, workspace_id: WorkspaceId, teamspace_id: TeamspaceId
    ) -> bool:
        role = strongest(
            await self._access.teamspace_role(caller, teamspace_id),
            await self._access.workspace_role(caller, workspace_id),
        )
        return role is not None and role_at_least(role, Role.EDITOR)

    async def _require(
        self, caller: CallerContext, folder_id: FolderId, *, edit: bool = False
    ) -> Folder:
        folder = await self._folders.get(caller.tenant_id, folder_id)
        if folder is None or not await self._can_see(caller, folder):
            raise NotFound("folder not found")
        if edit and not await self._can_edit(caller, folder):
            raise NotAuthorized("requires edit on the folder")
        return folder

    async def _can_see(self, caller: CallerContext, folder: Folder) -> bool:
        if folder.teamspace_id is None:
            return folder.created_by == caller.user_id  # private: creator-only
        role = self._access
        return (
            await role.teamspace_role(caller, folder.teamspace_id) is not None
            or await role.workspace_role(caller, folder.workspace_id) is not None
        )

    async def _can_edit(self, caller: CallerContext, folder: Folder) -> bool:
        if folder.teamspace_id is None:
            return folder.created_by == caller.user_id
        return await self._can_edit_teamspace(
            caller, folder.workspace_id, folder.teamspace_id
        )
