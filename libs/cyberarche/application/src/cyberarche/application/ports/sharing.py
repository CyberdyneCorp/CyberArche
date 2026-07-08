"""Sharing ports: share links and comments."""

from __future__ import annotations

from typing import Protocol

from cyberarche.domain.ids import DocumentId, ShareLinkId
from cyberarche.domain.sharing import Comment, ShareLink


class ShareLinkRepository(Protocol):
    async def add(self, link: ShareLink) -> None: ...

    async def get(self, link_id: ShareLinkId) -> ShareLink | None: ...

    async def list_for_document(self, document_id: DocumentId) -> list[ShareLink]: ...

    async def update(self, link: ShareLink) -> None: ...


class CommentRepository(Protocol):
    async def add(self, comment: Comment) -> None: ...

    async def get(self, document_id: DocumentId, comment_id: str) -> Comment | None: ...

    async def list_for_document(self, document_id: DocumentId) -> list[Comment]: ...

    async def update(self, comment: Comment) -> None: ...
