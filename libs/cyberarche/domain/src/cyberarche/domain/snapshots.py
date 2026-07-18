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
    # A human-friendly name for the version (set at record time or renamed).
    label: str | None = None


@dataclass(frozen=True, slots=True)
class BlockDiff:
    """Block-level changes between two block trees (version-history spec).

    Blocks are matched by their `id`. `modified` carries the block id with its
    text before and after, so a UI can render an inline before→after view.
    """

    added: list[dict[str, Any]]
    removed: list[dict[str, Any]]
    modified: list[dict[str, Any]]  # {id, before, after}


def _block_text(block: dict[str, Any]) -> str:
    """Best-effort plain text of a block, for readable diffs."""
    data = block.get("data")
    if not isinstance(data, dict):
        return ""
    for key in ("text", "source", "caption", "url"):
        value = data.get(key)
        if isinstance(value, str):
            return value
    return ""


def diff_blocks(old: list[dict[str, Any]], new: list[dict[str, Any]]) -> BlockDiff:
    """Compare two block trees by block `id` (version-history spec).

    A block is *added* when present only in `new`, *removed* when present only
    in `old`, and *modified* when its `id` is in both but its `data` differs.
    Unchanged blocks are skipped.
    """
    old_by_id = {b.get("id"): b for b in old}
    new_by_id = {b.get("id"): b for b in new}
    added = [b for b in new if b.get("id") not in old_by_id]
    removed = [b for b in old if b.get("id") not in new_by_id]
    modified: list[dict[str, Any]] = []
    for block_id, new_block in new_by_id.items():
        old_block = old_by_id.get(block_id)
        if old_block is None or old_block.get("data") == new_block.get("data"):
            continue
        modified.append(
            {
                "id": block_id,
                "before": _block_text(old_block),
                "after": _block_text(new_block),
            }
        )
    return BlockDiff(added=added, removed=removed, modified=modified)
