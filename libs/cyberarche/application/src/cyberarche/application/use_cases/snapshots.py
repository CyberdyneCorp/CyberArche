"""Snapshot use cases: list and restore document versions (document-model spec)."""

from __future__ import annotations

from typing import Any

from cyberarche.application.authz import AccessControl
from cyberarche.application.kernel import CallerContext
from cyberarche.application.ports.repositories import (
    DocumentRepository,
    SnapshotRepository,
)
from cyberarche.application.ports.telemetry import ClockPort, IdPort
from cyberarche.domain.errors import NotFound
from cyberarche.domain.ids import DocumentId, SnapshotId
from cyberarche.domain.memberships import Role
from cyberarche.domain.snapshots import Snapshot


class SnapshotUseCases:
    def __init__(
        self,
        snapshots: SnapshotRepository,
        documents: DocumentRepository,
        access: AccessControl,
        clock: ClockPort,
        ids: IdPort,
    ) -> None:
        self._snapshots = snapshots
        self._documents = documents
        self._access = access
        self._clock = clock
        self._ids = ids

    async def record(
        self,
        caller: CallerContext,
        document_id: DocumentId,
        *,
        content: dict[str, Any],
        state_vector: bytes,
        restored_from: SnapshotId | None = None,
    ) -> Snapshot:
        document = await self._require(caller, document_id, Role.EDITOR)
        latest = await self._snapshots.latest(document.id)
        snapshot = Snapshot(
            id=SnapshotId(self._ids.new_id()),
            document_id=document.id,
            seq=(latest.seq + 1) if latest else 1,
            content=content,
            state_vector=state_vector,
            created_at=self._clock.now(),
            restored_from=restored_from,
            created_by=caller.user_id,
        )
        await self._snapshots.add(snapshot)
        return snapshot

    async def list(
        self, caller: CallerContext, document_id: DocumentId
    ) -> list[Snapshot]:
        document = await self._require(caller, document_id, Role.VIEWER)
        return await self._snapshots.list_for_document(document.id)

    async def restore(
        self, caller: CallerContext, document_id: DocumentId, snapshot_id: SnapshotId
    ) -> Snapshot:
        """Replace current content with a prior snapshot; the restore is itself
        recorded as a new snapshot (document-model spec)."""
        document = await self._require(caller, document_id, Role.EDITOR)
        source = await self._snapshots.get(document.id, snapshot_id)
        if source is None:
            raise NotFound("snapshot not found")
        return await self.record(
            caller,
            document.id,
            content=source.content,
            state_vector=source.state_vector,
            restored_from=source.id,
        )

    async def _require(
        self, caller: CallerContext, document_id: DocumentId, role: Role
    ):
        document = await self._documents.get(caller.tenant_id, document_id)
        if document is None:
            raise NotFound("document not found")
        await self._access.require_document(caller, document, role)
        return document
