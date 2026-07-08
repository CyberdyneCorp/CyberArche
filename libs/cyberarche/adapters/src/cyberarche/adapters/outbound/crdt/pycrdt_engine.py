"""CrdtEnginePort adapter over pycrdt (Yjs-compatible).

Document body convention (shared with the web editor): the Yjs doc holds a
top-level Array("blocks") of Maps, each Map being one block
({id, type, data, ...}).
"""

from __future__ import annotations

from typing import Any

from pycrdt import Array, Doc, Map

from cyberarche.domain.errors import NotFound


#: Yjs encoding of an update carrying no changes (empty struct + delete sets).
_EMPTY_UPDATE = b"\x00\x00"


def _load(state: bytes) -> Doc:
    doc = Doc()
    if state:
        doc.apply_update(state)
    return doc


class PycrdtEngine:
    def merge(self, updates: list[bytes]) -> bytes:
        doc = Doc()
        for update in updates:
            if update:
                doc.apply_update(update)
        return doc.get_update()

    def state_vector(self, state: bytes) -> bytes:
        return _load(state).get_state()

    def diff(self, state: bytes, state_vector: bytes) -> bytes:
        doc = _load(state)
        return doc.get_update(state_vector) if state_vector else doc.get_update()

    def read_blocks(self, state: bytes) -> list[dict]:
        doc = _load(state)
        blocks = doc.get("blocks", type=Array)
        return [dict(item) if isinstance(item, Map) else item for item in blocks]

    def append_blocks(self, state: bytes, blocks: list[dict[str, Any]]) -> bytes:
        doc = _load(state)
        before = doc.get_state()
        array = doc.get("blocks", type=Array)
        for block in blocks:
            array.append(Map(block))
        return doc.get_update(before)

    def update_block(self, state: bytes, block_id: str, data: dict[str, Any]) -> bytes:
        doc = _load(state)
        before = doc.get_state()
        array = doc.get("blocks", type=Array)
        index = _index_of(array, block_id)
        if index is None:
            raise NotFound(f"block not found: {block_id}")
        block = array[index]
        # Merge into data so a text edit never drops a whiteboard scene etc.
        merged = {**(block.get("data") or {}), **data}
        block["data"] = merged
        return doc.get_update(before)

    def delete_block(self, state: bytes, block_id: str) -> bytes:
        doc = _load(state)
        before = doc.get_state()
        array = doc.get("blocks", type=Array)
        index = _index_of(array, block_id)
        if index is None:
            raise NotFound(f"block not found: {block_id}")
        del array[index]
        return doc.get_update(before)

    def is_empty(self, update: bytes) -> bool:
        # Yjs encodes "no structs, no delete-set" as two zero varints.
        return update == _EMPTY_UPDATE

    def replace_blocks(self, state: bytes, blocks: list[dict[str, Any]]) -> bytes:
        """Reconcile the body to `blocks` by id (design D-2).

        Clearing and re-appending would churn every block id and so orphan the
        comments anchored to them; it would also drop a concurrent peer's
        insert. Instead: delete what is gone, merge what survives, insert what
        is new, then fix the order.

        Blocks without an `id` cannot be matched and are always inserted, so
        replacing with such a list is not idempotent. Snapshots recorded by the
        system are materialized from the CRDT and always carry ids.
        """
        doc = _load(state)
        before = doc.get_state()
        changed = False
        with doc.transaction():
            array = doc.get("blocks", type=Array)
            # A block with no id has no identity to reconcile against; it can
            # only be inserted. System-recorded snapshots always carry ids.
            wanted = {b["id"]: b for b in blocks if b.get("id") is not None}

            # Drop blocks the snapshot does not have, and blocks whose type
            # changed (merging data across types is meaningless — D-2).
            for index in range(len(array) - 1, -1, -1):
                item = array[index]
                block_id = item.get("id")
                target = wanted.get(block_id)
                if target is None or target.get("type") != item.get("type"):
                    del array[index]
                    changed = True

            # Merge survivors, insert the rest, in the snapshot's order.
            for position, block in enumerate(blocks):
                block_id = block.get("id")
                index = _index_of(array, block_id) if block_id is not None else None
                if index is None:
                    array.insert(min(position, len(array)), Map(block))
                    changed = True
                    continue
                existing = array[index]
                data = {**(existing.get("data") or {}), **(block.get("data") or {})}
                if existing.get("data") != data:
                    existing["data"] = data
                    changed = True
                if index != position:
                    moved = _plain(existing)
                    del array[index]
                    array.insert(min(position, len(array)), Map(moved))
                    changed = True

        # `get_update(sv)` re-emits the document's whole delete set, so a doc
        # holding any tombstone yields a non-empty blob even when this call
        # mutated nothing. Report the canonical empty update instead (D-5).
        return doc.get_update(before) if changed else _EMPTY_UPDATE


def _plain(item: Map) -> dict[str, Any]:
    """A Map's contents as plain data, so it can be re-inserted elsewhere."""
    return {key: item[key] for key in item.keys()}


def _index_of(array: Array, block_id: str) -> int | None:
    for index, item in enumerate(array):
        if isinstance(item, Map) and item.get("id") == block_id:
            return index
    return None
