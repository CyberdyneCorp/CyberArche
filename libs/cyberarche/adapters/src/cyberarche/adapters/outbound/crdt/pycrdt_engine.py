"""CrdtEnginePort adapter over pycrdt (Yjs-compatible).

Document body convention (shared with the web editor): the Yjs doc holds a
top-level Array("blocks") of Maps, each Map being one block
({id, type, data, ...}).
"""

from __future__ import annotations

from typing import Any

from pycrdt import Array, Doc, Map

from cyberarche.domain.errors import NotFound


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


def _index_of(array: Array, block_id: str) -> int | None:
    for index, item in enumerate(array):
        if isinstance(item, Map) and item.get("id") == block_id:
            return index
    return None
