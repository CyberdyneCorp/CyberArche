"""Wikilink backlinks (document-links spec).

Backlinks are computed on demand: scan the workspace's documents' block text for
`[[<this document's title>]]`. Correct and index-free; O(workspace docs) per
view, so a persistent link index is a future optimization. Reuses the same CRDT
read path the agent uses (realtime.current_state -> engine.read_blocks).
"""

from __future__ import annotations

import re

from cyberarche.application.authz import AccessControl
from cyberarche.application.kernel import CallerContext
from cyberarche.application.ports.crdt import CrdtEnginePort
from cyberarche.application.ports.repositories import DocumentRepository
from cyberarche.application.use_cases.realtime import RealtimeUseCases
from cyberarche.domain.documents import Document
from cyberarche.domain.errors import NotAuthorized, NotFound
from cyberarche.domain.ids import DocumentId
from cyberarche.domain.memberships import Role

_WIKILINK = re.compile(r"\[\[([^\[\]]+)\]\]")


def _block_texts(block: dict) -> list[str]:
    data = block.get("data")
    if not isinstance(data, dict):
        return []
    texts: list[str] = []
    if isinstance(data.get("text"), str):
        texts.append(data["text"])
    header = data.get("header")
    if isinstance(header, list):
        texts.extend(str(c) for c in header)
    rows = data.get("rows")
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, list):
                texts.extend(str(c) for c in row)
    return texts


def _references(blocks: list[dict], wanted_title_lower: str) -> bool:
    for block in blocks:
        for text in _block_texts(block):
            for match in _WIKILINK.finditer(text):
                if match.group(1).strip().lower() == wanted_title_lower:
                    return True
    return False


class LinksUseCases:
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

    async def backlinks(
        self, caller: CallerContext, document_id: DocumentId
    ) -> list[Document]:
        """Documents in the same workspace that reference this one via `[[title]]`."""
        target = await self._documents.get(caller.tenant_id, document_id)
        if target is None or target.trashed:
            raise NotFound("document not found")
        await self._access.require_document(caller, target, Role.VIEWER)
        wanted = target.title.strip().lower()
        if not wanted:
            return []

        results: list[Document] = []
        for doc in await self._documents.list_in_workspace(
            caller.tenant_id, target.workspace_id
        ):
            if doc.id == target.id:
                continue
            if await self._access.document_role(caller, doc) is None:
                continue
            try:
                state = await self._realtime.current_state(caller, doc.id)
            except NotAuthorized:
                continue
            if _references(self._engine.read_blocks(state), wanted):
                results.append(doc)
        return results
