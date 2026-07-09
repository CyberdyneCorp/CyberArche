"""Document use cases (document-model spec).

All access checks run here so every inbound surface enforces identically.
Tenant scope always comes from the caller, never from request input.
"""

from __future__ import annotations

from dataclasses import replace

from cyberarche.application.authz import AccessControl
from cyberarche.application.kernel import CallerContext
from cyberarche.application.ports.folders import FolderRepository
from cyberarche.application.ports.repositories import DocumentRepository
from cyberarche.application.ports.teamspaces import TeamspaceRepository
from cyberarche.application.ports.telemetry import ClockPort, IdPort
from cyberarche.domain.documents import Document
from cyberarche.domain.errors import NotFound, ValidationFailed
from cyberarche.domain.ids import DocumentId, FolderId, TeamspaceId, WorkspaceId
from cyberarche.domain.memberships import Role


class DocumentUseCases:
    def __init__(
        self,
        documents: DocumentRepository,
        access: AccessControl,
        clock: ClockPort,
        ids: IdPort,
        teamspaces: TeamspaceRepository | None = None,
        folders: "FolderRepository | None" = None,
    ) -> None:
        self._documents = documents
        self._access = access
        self._clock = clock
        self._ids = ids
        self._teamspaces = teamspaces
        self._folders = folders

    async def create(
        self,
        caller: CallerContext,
        *,
        workspace_id: WorkspaceId,
        title: str,
        parent_id: DocumentId | None = None,
        teamspace_id: TeamspaceId | None = None,
    ) -> Document:
        """Create a document, optionally inside a teamspace of the workspace.

        A teamspace member without a workspace role may create in it, so the
        permission check falls back to the teamspace when one is given.
        """
        if teamspace_id is None:
            await self._access.require_workspace(caller, workspace_id, Role.EDITOR)
        else:
            await self._require_teamspace_of(caller, workspace_id, teamspace_id)
        if parent_id is not None:
            parent = await self._get_or_raise(caller, parent_id)
            if parent.workspace_id != workspace_id:
                raise ValidationFailed("parent document belongs to another workspace")
        siblings = await self._documents.children(
            caller.tenant_id, workspace_id, parent_id
        )
        document = Document.create(
            id=DocumentId(self._ids.new_id()),
            workspace_id=workspace_id,
            tenant_id=caller.tenant_id,
            title=title,
            parent_id=parent_id,
            position=len(siblings),
            created_by=caller.user_id,
            created_at=self._clock.now(),
            teamspace_id=teamspace_id,
        )
        await self._documents.add(document)
        return document

    async def _require_teamspace_of(
        self,
        caller: CallerContext,
        workspace_id: WorkspaceId,
        teamspace_id: TeamspaceId,
    ) -> None:
        if self._teamspaces is None:
            raise ValidationFailed("teamspaces are not configured")
        teamspace = await self._teamspaces.get(caller.tenant_id, teamspace_id)
        if teamspace is None:
            raise NotFound("teamspace not found")
        if teamspace.workspace_id != workspace_id:
            raise ValidationFailed("teamspace belongs to another workspace")
        await self._access.require_teamspace(caller, teamspace, Role.EDITOR)

    async def get(self, caller: CallerContext, document_id: DocumentId) -> Document:
        document = await self._get_or_raise(caller, document_id)
        await self._access.require_document(caller, document, Role.VIEWER)
        return document

    async def children(
        self,
        caller: CallerContext,
        *,
        workspace_id: WorkspaceId,
        parent_id: DocumentId | None = None,
    ) -> list[Document]:
        await self._access.require_workspace(caller, workspace_id, Role.VIEWER)
        return await self._documents.children(caller.tenant_id, workspace_id, parent_id)

    async def retitle(
        self, caller: CallerContext, document_id: DocumentId, *, title: str
    ) -> Document:
        document = await self._get_or_raise(caller, document_id)
        await self._access.require_document(caller, document, Role.EDITOR)
        updated = document.retitle(title, now=self._clock.now())
        await self._documents.update(updated)
        return updated

    async def move(
        self,
        caller: CallerContext,
        document_id: DocumentId,
        *,
        parent_id: DocumentId | None,
        position: int,
    ) -> Document:
        """Move a document under a new parent and/or to a new sibling position."""
        document = await self._get_or_raise(caller, document_id)
        await self._access.require_document(caller, document, Role.EDITOR)
        if parent_id is not None:
            parent = await self._get_or_raise(caller, parent_id)
            if parent.workspace_id != document.workspace_id:
                raise ValidationFailed("cannot move across workspaces")
            await self._ensure_not_descendant(caller, of=document, candidate=parent)
        moved = document.moved(
            parent_id=parent_id, position=position, now=self._clock.now()
        )
        await self._documents.update(moved)
        await self._renumber_siblings(caller, moved, insert_at=position)
        return moved

    async def trash(self, caller: CallerContext, document_id: DocumentId) -> Document:
        document = await self._get_or_raise(caller, document_id)
        await self._access.require_document(caller, document, Role.EDITOR)
        trashed = document.trash(now=self._clock.now())
        await self._documents.update(trashed)
        return trashed

    async def restore(self, caller: CallerContext, document_id: DocumentId) -> Document:
        document = await self._get_or_raise(caller, document_id, include_trashed=True)
        if not document.trashed:
            raise ValidationFailed("document is not in the trash")
        await self._access.require_document(caller, document, Role.EDITOR)
        restored = document.restore(now=self._clock.now())
        await self._documents.update(restored)
        return restored

    async def purge(
        self, caller: CallerContext, document_id: DocumentId
    ) -> list[DocumentId]:
        """Permanently delete a trashed document and its subtree (D-1..D-4).

        Only reachable from the trash: a live document must be trashed first, so
        the trash stays the recoverable safety net.
        """
        document = await self._get_or_raise(
            caller, document_id, include_trashed=True
        )
        if not document.trashed:
            raise ValidationFailed("only a trashed document can be purged")
        await self._access.require_document(caller, document, Role.EDITOR)
        return await self._documents.purge(caller.tenant_id, document_id)

    async def place_in_folder(
        self, caller: CallerContext, document_id: DocumentId, folder_id: FolderId
    ) -> Document:
        """Put a document in a folder; it adopts the folder's teamspace scope so
        access follows the container (add-folders-and-private D-2)."""
        document = await self._get_or_raise(caller, document_id)
        await self._access.require_document(caller, document, Role.EDITOR)
        if self._folders is None:
            raise ValidationFailed("folders are not configured")
        folder = await self._folders.get(caller.tenant_id, folder_id)
        if folder is None:
            raise NotFound("folder not found")
        moved = replace(
            document,
            folder_id=folder_id,
            teamspace_id=folder.teamspace_id,
            updated_at=self._clock.now(),
        )
        await self._documents.update(moved)
        return moved

    async def move_to_private(
        self, caller: CallerContext, document_id: DocumentId
    ) -> Document:
        """Remove a document from any folder/teamspace: it becomes private to
        the caller (who must be able to edit it)."""
        document = await self._get_or_raise(caller, document_id)
        await self._access.require_document(caller, document, Role.EDITOR)
        moved = replace(
            document,
            folder_id=None,
            teamspace_id=None,
            updated_at=self._clock.now(),
        )
        await self._documents.update(moved)
        return moved

    async def list_private(
        self, caller: CallerContext, *, workspace_id: WorkspaceId
    ) -> list[Document]:
        """The caller's own private root documents: no teamspace, no folder."""
        await self._access.require_workspace(caller, workspace_id, Role.VIEWER)
        roots = await self._documents.children(caller.tenant_id, workspace_id, None)
        return [
            d
            for d in roots
            if d.teamspace_id is None
            and d.folder_id is None
            and d.created_by == caller.user_id
        ]

    async def list_for_folder(
        self, caller: CallerContext, folder_id: FolderId
    ) -> list[Document]:
        """Documents in a folder that the caller may view."""
        docs = await self._documents.list_for_folder(caller.tenant_id, folder_id)
        visible: list[Document] = []
        for document in docs:
            if await self._access.document_role(caller, document) is not None:
                visible.append(document)
        return visible

    async def list_trashed(
        self, caller: CallerContext, *, workspace_id: WorkspaceId
    ) -> list[Document]:
        await self._access.require_workspace(caller, workspace_id, Role.VIEWER)
        return await self._documents.list_trashed(caller.tenant_id, workspace_id)

    async def search(
        self, caller: CallerContext, *, query: str, limit: int = 20
    ) -> list[Document]:
        """Title search within the caller's tenant, filtered to documents the
        caller may at least view (mcp-server spec: no unauthorized results)."""
        candidates = await self._documents.search_by_title(
            caller.tenant_id, query, limit=limit * 2
        )
        visible: list[Document] = []
        for document in candidates:
            role = await self._access.document_role(caller, document)
            if role is not None:
                visible.append(document)
            if len(visible) >= limit:
                break
        return visible

    async def _get_or_raise(
        self,
        caller: CallerContext,
        document_id: DocumentId,
        *,
        include_trashed: bool = False,
    ) -> Document:
        document = await self._documents.get(caller.tenant_id, document_id)
        if document is None or (document.trashed and not include_trashed):
            raise NotFound("document not found")
        return document

    async def _ensure_not_descendant(
        self, caller: CallerContext, *, of: Document, candidate: Document
    ) -> None:
        """Reject moving a document under its own descendant (would orphan the subtree)."""
        current: Document | None = candidate
        while current is not None and current.parent_id is not None:
            if current.parent_id == of.id:
                raise ValidationFailed("cannot move a document under its own descendant")
            current = await self._documents.get(caller.tenant_id, current.parent_id)

    async def _renumber_siblings(
        self, caller: CallerContext, moved: Document, *, insert_at: int
    ) -> None:
        """Rewrite sibling positions into a dense 0..n sequence with `moved` at insert_at."""
        siblings = await self._documents.children(
            caller.tenant_id, moved.workspace_id, moved.parent_id
        )
        others = [d for d in siblings if d.id != moved.id]
        insert_at = max(0, min(insert_at, len(others)))
        ordered = others[:insert_at] + [moved] + others[insert_at:]
        now = self._clock.now()
        renumbered = [
            doc.moved(parent_id=doc.parent_id, position=index, now=now)
            for index, doc in enumerate(ordered)
            if doc.position != index
        ]
        if renumbered:
            await self._documents.update_many(renumbered)
