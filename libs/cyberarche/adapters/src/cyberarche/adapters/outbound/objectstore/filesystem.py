"""BlobStoragePort adapter over the local filesystem.

Keys are sanitized into a two-level directory layout. An S3-compatible
adapter can implement the same port later without touching use cases
(architecture-quality spec).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from cyberarche.application.ports.storage import Blob


def _paths(root: Path, key: str) -> tuple[Path, Path]:
    digest = hashlib.sha256(key.encode()).hexdigest()
    base = root / digest[:2] / digest
    return base.with_suffix(".bin"), base.with_suffix(".meta.json")


class FilesystemBlobStorage:
    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    async def put(self, key: str, content: bytes, *, content_type: str) -> None:
        data_path, meta_path = _paths(self._root, key)
        data_path.parent.mkdir(parents=True, exist_ok=True)
        data_path.write_bytes(content)
        meta_path.write_text(json.dumps({"key": key, "content_type": content_type}))

    async def get(self, key: str) -> Blob | None:
        data_path, meta_path = _paths(self._root, key)
        if not data_path.exists():
            return None
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        return Blob(
            key=key,
            content=data_path.read_bytes(),
            content_type=meta.get("content_type", "application/octet-stream"),
        )

    async def delete(self, key: str) -> None:
        data_path, meta_path = _paths(self._root, key)
        data_path.unlink(missing_ok=True)
        meta_path.unlink(missing_ok=True)
