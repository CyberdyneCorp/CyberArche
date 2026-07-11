"""Realtime sync use cases (realtime-collaboration spec).

Join/apply enforce document permissions here — the WebSocket relay is a
thin inbound adapter, so realtime cannot diverge from HTTP/MCP enforcement
(permissions-sharing spec).
"""

from __future__ import annotations

from cyberarche.application.authz import AccessControl
from cyberarche.application.kernel import CallerContext
from cyberarche.application.ports.bus import PeerBusPort
from cyberarche.application.ports.crdt import CrdtEnginePort, UpdateLogPort
from cyberarche.application.ports.repositories import (
    DocumentRepository,
    SnapshotRepository,
)
from cyberarche.application.ports.telemetry import ClockPort, IdPort
from cyberarche.domain.documents import Document
from cyberarche.domain.errors import NotFound
from cyberarche.domain.ids import DocumentId, SnapshotId
from cyberarche.domain.memberships import Role, role_at_least
from cyberarche.domain.snapshots import Snapshot

# Compact the update log into one merged row once it grows past this.
# Each compaction also records an immutable content snapshot, giving the
# document-model spec's "periodic snapshot" cadence driven by edit volume.
COMPACTION_THRESHOLD = 200


def updates_channel(document_id: DocumentId) -> str:
    """Bus channel carrying RAW persisted updates for a document. Every
    accepted edit — from a WebSocket peer, the HTTP agent, or MCP — is
    published here, so relay instances fan out server-originated edits
    live (Yjs re-application is idempotent, duplicates are harmless)."""
    return f"cyberarche:doc-updates:{document_id}"


class RealtimeUseCases:
    def __init__(
        self,
        documents: DocumentRepository,
        update_log: UpdateLogPort,
        engine: CrdtEnginePort,
        access: AccessControl,
        snapshots: SnapshotRepository | None = None,
        clock: ClockPort | None = None,
        ids: IdPort | None = None,
        bus: PeerBusPort | None = None,
    ) -> None:
        self._documents = documents
        self._update_log = update_log
        self._engine = engine
        self._access = access
        self._snapshots = snapshots
        self._clock = clock
        self._ids = ids
        self._bus = bus

    async def join(
        self, caller: CallerContext, document_id: DocumentId
    ) -> tuple[Document, bytes]:
        """Authorize a viewer and return the current document state as one
        update blob (late joiners render the latest content)."""
        document = await self._require(caller, document_id, Role.VIEWER)
        return document, await self._current_state(document_id)

    async def can_edit(self, caller: CallerContext, document_id: DocumentId) -> bool:
        document = await self._require(caller, document_id, Role.VIEWER)
        role = await self._access.document_role(caller, document)
        return role is not None and role_at_least(role, Role.EDITOR)

    async def apply(
        self,
        caller: CallerContext,
        document_id: DocumentId,
        update: bytes,
        *,
        origin: str | None = None,
    ) -> bytes:
        """Persist an editor's update (human or AI peer) and return it for
        broadcast. Offline batches merge conflict-free by CRDT semantics.

        `origin` attributes the update (e.g. "agent:<user>" for AI edits);
        permission is always checked against the human caller.
        """
        await self._require(caller, document_id, Role.EDITOR)
        await self._update_log.append(
            document_id, update, origin=origin or caller.user_id
        )
        if self._bus is not None:  # live fanout to every relay instance
            await self._bus.publish(updates_channel(document_id), update)
        await self._maybe_compact(document_id)
        return update

    async def current_state(
        self, caller: CallerContext, document_id: DocumentId
    ) -> bytes:
        await self._require(caller, document_id, Role.VIEWER)
        return await self._current_state(document_id)

    async def read_blocks(
        self, caller: CallerContext, document_id: DocumentId
    ) -> list[dict]:
        """The document's current block tree — for reading content outside the
        editor (e.g. exporting a whole teamspace/folder)."""
        return self._engine.read_blocks(await self.current_state(caller, document_id))

    async def _current_state(self, document_id: DocumentId) -> bytes:
        """Reconstruct from the persisted log — survives relay restarts."""
        updates = await self._update_log.list_for_document(document_id)
        return self._engine.merge([u.update for u in updates])

    async def _maybe_compact(self, document_id: DocumentId) -> None:
        if await self._update_log.count(document_id) < COMPACTION_THRESHOLD:
            return
        updates = await self._update_log.list_for_document(document_id)
        merged = self._engine.merge([u.update for u in updates])
        await self._update_log.replace_with(
            document_id, merged, up_to_seq=updates[-1].seq
        )
        await self._record_snapshot(document_id, merged)

    async def _record_snapshot(self, document_id: DocumentId, state: bytes) -> None:
        """Server-initiated content snapshot alongside each compaction."""
        if self._snapshots is None or self._clock is None or self._ids is None:
            return
        latest = await self._snapshots.latest(document_id)
        await self._snapshots.add(
            Snapshot(
                id=SnapshotId(self._ids.new_id()),
                document_id=document_id,
                seq=(latest.seq + 1) if latest else 1,
                content={"blocks": self._engine.read_blocks(state)},
                state_vector=self._engine.state_vector(state),
                created_at=self._clock.now(),
            )
        )

    async def _require(
        self, caller: CallerContext, document_id: DocumentId, role: Role
    ) -> Document:
        document = await self._documents.get(caller.tenant_id, document_id)
        if document is None or document.trashed:
            raise NotFound("document not found")
        await self._access.require_document(caller, document, role)
        return document
