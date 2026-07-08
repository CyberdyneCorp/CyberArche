"""Blob storage port: uploaded originals are kept by us, not only by RAG."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Blob:
    key: str
    content: bytes
    content_type: str


class BlobStoragePort(Protocol):
    async def put(self, key: str, content: bytes, *, content_type: str) -> None: ...

    async def get(self, key: str) -> Blob | None: ...

    async def delete(self, key: str) -> None: ...
