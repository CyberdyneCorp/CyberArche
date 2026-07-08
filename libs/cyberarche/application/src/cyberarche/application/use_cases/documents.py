"""Document use cases (document-model spec).

All access checks run here so every inbound surface enforces identically.
Tenant scope always comes from the caller, never from request input.
"""

from __future__ import annotations

from cyberarche.application.authz import AccessControl
from cyberarche.application.kernel import CallerContext
from cyberarche.application.ports.repositories import DocumentRepository
from cyberarche.application.ports.telemetry import ClockPort, IdPort
from cyberarche.domain.documents import Document
from cyberarche.domain.errors import NotFound, ValidationFailed
from cyberarche.domain.ids import DocumentId, WorkspaceId
from cyberarche.domain.memberships import Role


class DocumentUseCases:
    def __init__(
        self,
        documents: DocumentRepository,
        access: AccessControl,
        clock: ClockPort,
        ids: IdPort,
    ) -> None:
        self._documents = documents
        self._access = access
        self._clock = clock
        self._ids = ids

    async def create(
        self,
        caller: CallerContext,
        *,
        workspace_id: WorkspaceId,
        title: str,
        parent_id: DocumentId | None = None,
    ) -> Document:
        await self._access.require_workspace(caller, workspace_id, Role.EDITOR)
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
        )
        await self._documents.add(document)
        return document

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

    async def list_trashed(
        self, caller: CallerContext, *, workspace_id: WorkspaceId
    ) -> list[Document]:
        await self._access.require_workspace(caller, workspace_id, Role.VIEWER)
        return await self._documents.list_trashed(caller.tenant_id, workspace_id)

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
