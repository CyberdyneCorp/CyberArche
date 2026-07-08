"""CRDT ports (realtime-collaboration spec).

The engine is stateless over opaque byte blobs: documents are represented
by their full update encoding, so any relay instance (or worker) can load,
merge, and diff without in-process affinity (architecture-quality spec).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from cyberarche.domain.ids import DocumentId


class CrdtEnginePort(Protocol):
    def merge(self, updates: list[bytes]) -> bytes:
        """Merge updates (in order) into a single canonical update blob."""
        ...

    def state_vector(self, state: bytes) -> bytes:
        """State vector of a document state (an update blob)."""
        ...

    def diff(self, state: bytes, state_vector: bytes) -> bytes:
        """Update that brings a peer at `state_vector` up to `state`."""
        ...


@dataclass(frozen=True, slots=True)
class LoggedUpdate:
    seq: int
    document_id: DocumentId
    update: bytes
    origin: str | None
    created_at: datetime


class UpdateLogPort(Protocol):
    """Persisted CRDT update stream, compactable into a single merged row."""

    async def append(
        self, document_id: DocumentId, update: bytes, *, origin: str | None
    ) -> LoggedUpdate: ...

    async def list_for_document(self, document_id: DocumentId) -> list[LoggedUpdate]: ...

    async def count(self, document_id: DocumentId) -> int: ...

    async def replace_with(
        self, document_id: DocumentId, merged: bytes, *, up_to_seq: int
    ) -> None:
        """Compaction: replace all updates with seq <= up_to_seq by one merged row."""
        ...
