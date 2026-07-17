"""Full-text search over document titles and block content (document-search spec).

Like backlinks/graph, matches are computed on demand by scanning the workspace's
documents. A hit is a title match (needle in the title) or a content match
(needle in the block text), the latter carrying a short surrounding snippet.
Access-scoped and index-free; reuses the same CRDT read path the graph uses
(realtime.current_state -> engine.read_blocks). O(workspace docs) per query.
"""

from __future__ import annotations

from dataclasses import dataclass

from cyberarche.application.authz import AccessControl
from cyberarche.application.kernel import CallerContext
from cyberarche.application.ports.crdt import CrdtEnginePort
from cyberarche.application.ports.repositories import DocumentRepository
from cyberarche.application.use_cases.realtime import RealtimeUseCases
from cyberarche.domain.documents import Document
from cyberarche.domain.errors import NotAuthorized
from cyberarche.domain.ids import WorkspaceId
from cyberarche.domain.memberships import Role

_SNIPPET_PAD = 60  # characters of context kept on each side of a content match


@dataclass(frozen=True, slots=True)
class SearchHit:
    document: Document
    field: str  # "title" | "content"
    snippet: str


def _table_texts(data: dict) -> list[str]:
    """Header cells and row cells of a table block."""
    texts: list[str] = []
    header = data.get("header")
    if isinstance(header, list):
        texts.extend(str(c) for c in header)
    rows = data.get("rows")
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, list):
                texts.extend(str(c) for c in row)
    return texts


def _block_texts(block: dict) -> list[str]:
    """Searchable strings in a block: paragraph/heading text, code/latex/mermaid
    source, and table header + row cells (mirrors the graph's block reader)."""
    data = block.get("data")
    if not isinstance(data, dict):
        return []
    texts = [data[k] for k in ("text", "source") if isinstance(data.get(k), str)]
    texts.extend(_table_texts(data))
    return texts


def _document_text(blocks: list[dict]) -> str:
    parts: list[str] = []
    for block in blocks:
        parts.extend(_block_texts(block))
    return "\n".join(t for t in parts if t.strip())


def _snippet(text: str, needle: str) -> str:
    """~60 chars of context around the first match, newlines flattened to spaces,
    with ellipses where the text was truncated."""
    idx = text.lower().find(needle)
    if idx == -1:
        return ""
    start = max(0, idx - _SNIPPET_PAD)
    end = min(len(text), idx + len(needle) + _SNIPPET_PAD)
    body = " ".join(text[start:end].split())
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{body}{suffix}"


class SearchUseCases:
    def __init__(
        self,
        documents: DocumentRepository,
        realtime: RealtimeUseCases,
        engine: CrdtEnginePort,
        access: AccessControl,
    ) -> None:
        self._documents = documents
        self._realtime = realtime
        self._engine = engine
        self._access = access

    async def search(
        self,
        caller: CallerContext,
        workspace_id: WorkspaceId,
        *,
        query: str,
        limit: int = 20,
    ) -> list[SearchHit]:
        """Documents in the workspace whose title or block content contains the
        query, restricted to the docs the caller may view. Content matches carry
        a snippet; empty queries return nothing."""
        await self._access.require_workspace(caller, workspace_id, Role.VIEWER)
        needle = query.strip().lower()
        if not needle:
            return []
        hits: list[SearchHit] = []
        for doc in await self._documents.list_in_workspace(
            caller.tenant_id, workspace_id
        ):
            if await self._access.document_role(caller, doc) is None:
                continue
            hit = await self._document_hit(caller, doc, needle)
            if hit is not None:
                hits.append(hit)
                if len(hits) >= limit:
                    break
        return hits

    async def _document_hit(
        self, caller: CallerContext, doc: Document, needle: str
    ) -> SearchHit | None:
        """A title hit, else a content hit with a snippet, else None."""
        if needle in doc.title.lower():
            return SearchHit(document=doc, field="title", snippet="")
        try:
            state = await self._realtime.current_state(caller, doc.id)
        except NotAuthorized:
            return None
        text = _document_text(self._engine.read_blocks(state))
        if needle in text.lower():
            return SearchHit(document=doc, field="content", snippet=_snippet(text, needle))
        return None
