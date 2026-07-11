"""Wikilink backlinks (document-links spec).

Backlinks are computed on demand: scan the workspace's documents' block text for
`[[<this document's title>]]`. Correct and index-free; O(workspace docs) per
view, so a persistent link index is a future optimization. Reuses the same CRDT
read path the agent uses (realtime.current_state -> engine.read_blocks).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from cyberarche.application.authz import AccessControl
from cyberarche.application.kernel import CallerContext
from cyberarche.application.ports.crdt import CrdtEnginePort
from cyberarche.application.ports.repositories import DocumentRepository
from cyberarche.application.use_cases.realtime import RealtimeUseCases
from cyberarche.domain.documents import Document
from cyberarche.domain.errors import NotAuthorized, NotFound, ValidationFailed
from cyberarche.domain.ids import DocumentId, FolderId, TeamspaceId
from cyberarche.domain.memberships import Role

_WIKILINK = re.compile(r"\[\[([^\[\]]+)\]\]")


@dataclass(frozen=True, slots=True)
class GraphNode:
    id: str
    title: str


@dataclass(frozen=True, slots=True)
class GraphEdge:
    source: str
    target: str


@dataclass(frozen=True, slots=True)
class LinkGraph:
    nodes: list[GraphNode]
    edges: list[GraphEdge]


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


def _outgoing_titles(blocks: list[dict]) -> set[str]:
    """Lowercased titles this document links to via `[[title]]`."""
    titles: set[str] = set()
    for block in blocks:
        for text in _block_texts(block):
            for match in _WIKILINK.finditer(text):
                title = match.group(1).strip().lower()
                if title:
                    titles.add(title)
    return titles


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

    async def graph(
        self,
        caller: CallerContext,
        *,
        teamspace_id: TeamspaceId | None = None,
        folder_id: FolderId | None = None,
    ) -> LinkGraph:
        """The `[[title]]` link graph over the documents in a teamspace or folder.

        Nodes are the in-scope documents the caller may view; edges are resolved
        links between two in-scope documents (self-links and links leaving the
        scope are dropped; duplicates collapse)."""
        if teamspace_id is not None:
            scope = await self._documents.list_for_teamspace(
                caller.tenant_id, teamspace_id
            )
        elif folder_id is not None:
            scope = await self._documents.list_for_folder(caller.tenant_id, folder_id)
        else:
            raise ValidationFailed("teamspace_id or folder_id required")

        visible = [
            doc
            for doc in scope
            if not doc.trashed
            and await self._access.document_role(caller, doc) is not None
        ]
        if not visible:
            return LinkGraph(nodes=[], edges=[])

        # Title -> id resolution across the workspace (same rule as wikilinks).
        title_to_id: dict[str, str] = {}
        for doc in await self._documents.list_in_workspace(
            caller.tenant_id, visible[0].workspace_id
        ):
            key = doc.title.strip().lower()
            if key and key not in title_to_id:
                title_to_id[key] = str(doc.id)

        in_scope = {str(doc.id) for doc in visible}
        nodes = [GraphNode(id=str(doc.id), title=doc.title) for doc in visible]
        seen: set[tuple[str, str]] = set()
        edges: list[GraphEdge] = []
        for doc in visible:
            source = str(doc.id)
            try:
                state = await self._realtime.current_state(caller, doc.id)
            except NotAuthorized:
                continue
            for title in _outgoing_titles(self._engine.read_blocks(state)):
                target = title_to_id.get(title)
                if target is None or target == source or target not in in_scope:
                    continue
                if (source, target) in seen:
                    continue
                seen.add((source, target))
                edges.append(GraphEdge(source=source, target=target))
        return LinkGraph(nodes=nodes, edges=edges)
