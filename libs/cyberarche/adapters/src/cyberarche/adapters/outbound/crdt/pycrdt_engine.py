"""CrdtEnginePort adapter over pycrdt (Yjs-compatible)."""

from __future__ import annotations

from pycrdt import Doc


class PycrdtEngine:
    def merge(self, updates: list[bytes]) -> bytes:
        doc = Doc()
        for update in updates:
            if update:
                doc.apply_update(update)
        return doc.get_update()

    def state_vector(self, state: bytes) -> bytes:
        doc = Doc()
        if state:
            doc.apply_update(state)
        return doc.get_state()

    def diff(self, state: bytes, state_vector: bytes) -> bytes:
        doc = Doc()
        if state:
            doc.apply_update(state)
        return doc.get_update(state_vector) if state_vector else doc.get_update()
