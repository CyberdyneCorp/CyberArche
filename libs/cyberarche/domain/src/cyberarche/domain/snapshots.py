"""Immutable document snapshots (document-model spec).

A snapshot materializes the block tree as JSON plus the CRDT state vector,
so a document can be read, indexed, and restored without a live CRDT session.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from cyberarche.domain.ids import DocumentId, SnapshotId, UserId


@dataclass(frozen=True, slots=True)
class Snapshot:
    id: SnapshotId
    document_id: DocumentId
    seq: int
    content: dict[str, Any]
    state_vector: bytes
    created_at: datetime
    # Set when the snapshot was produced by a restore action.
    restored_from: SnapshotId | None = None
    created_by: UserId | None = None
