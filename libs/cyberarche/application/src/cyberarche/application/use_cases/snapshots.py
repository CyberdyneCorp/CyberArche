"""Snapshot use cases: list and restore document versions (document-model spec)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cyberarche.application.authz import AccessControl
from cyberarche.application.ports.crdt import CrdtEnginePort
from cyberarche.application.kernel import CallerContext
from cyberarche.application.ports.repositories import (
    DocumentRepository,
    SnapshotRepository,
)
from cyberarche.application.ports.telemetry import ClockPort, IdPort
from cyberarche.domain.errors import NotFound
from cyberarche.domain.ids import DocumentId, SnapshotId
from cyberarche.domain.memberships import Role
from cyberarche.domain.snapshots import BlockDiff, Snapshot, diff_blocks

if TYPE_CHECKING:  # composition only; avoids a use-case import cycle
    from cyberarche.application.use_cases.realtime import RealtimeUseCases


class SnapshotUseCases:
    def __init__(
        self,
        snapshots: SnapshotRepository,
        documents: DocumentRepository,
        access: AccessControl,
        clock: ClockPort,
        ids: IdPort,
        engine: CrdtEnginePort,
        realtime: "RealtimeUseCases",
    ) -> None:
        self._snapshots = snapshots
        self._documents = documents
        self._access = access
        self._clock = clock
        self._ids = ids
        self._engine = engine
        self._realtime = realtime

    async def record(
        self,
        caller: CallerContext,
        document_id: DocumentId,
        *,
        content: dict[str, Any],
        state_vector: bytes,
        restored_from: SnapshotId | None = None,
        label: str | None = None,
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
            label=label,
        )
        await self._snapshots.add(snapshot)
        return snapshot

    async def rename(
        self,
        caller: CallerContext,
        document_id: DocumentId,
        snapshot_id: SnapshotId,
        label: str | None,
    ) -> Snapshot:
        """Name (or clear the name of) a version; requires EDITOR."""
        document = await self._require(caller, document_id, Role.EDITOR)
        snapshot = await self._snapshots.get(document.id, snapshot_id)
        if snapshot is None:
            raise NotFound("snapshot not found")
        return await self._snapshots.set_label(document.id, snapshot_id, label)

    async def diff(
        self,
        caller: CallerContext,
        document_id: DocumentId,
        from_id: SnapshotId,
        to_id: SnapshotId | None = None,
    ) -> BlockDiff:
        """Block-level diff of snapshot `from_id` against snapshot `to_id`, or
        against the document's current content when `to_id` is omitted. Requires
        VIEWER (read-only)."""
        document = await self._require(caller, document_id, Role.VIEWER)
        source = await self._snapshots.get(document.id, from_id)
        if source is None:
            raise NotFound("snapshot not found")
        if to_id is not None:
            target = await self._snapshots.get(document.id, to_id)
            if target is None:
                raise NotFound("snapshot not found")
            new_blocks = target.content.get("blocks", [])
        else:
            new_blocks = await self._realtime.read_blocks(caller, document.id)
        return diff_blocks(source.content.get("blocks", []), new_blocks)

    async def list(
        self, caller: CallerContext, document_id: DocumentId
    ) -> list[Snapshot]:
        document = await self._require(caller, document_id, Role.VIEWER)
        return await self._snapshots.list_for_document(document.id)

    async def restore(
        self, caller: CallerContext, document_id: DocumentId, snapshot_id: SnapshotId
    ) -> Snapshot:
        """Replace current content with a prior snapshot; the restore is itself
        recorded as a new snapshot (document-model spec).

        The replacement goes through the CRDT and the realtime apply path
        (design D-1), so it is persisted to the update log and broadcast to
        every connected editor — writing the document row directly would leave
        open browsers holding a divergent replica.
        """
        document = await self._require(caller, document_id, Role.EDITOR)
        source = await self._snapshots.get(document.id, snapshot_id)
        if source is None:
            raise NotFound("snapshot not found")

        state = await self._realtime.current_state(caller, document.id)
        update = self._engine.replace_blocks(state, source.content.get("blocks", []))
        if not self._engine.is_empty(update):  # D-5: no empty log entries
            await self._realtime.apply(
                caller, document.id, update, origin=f"restore:{caller.user_id}"
            )

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
