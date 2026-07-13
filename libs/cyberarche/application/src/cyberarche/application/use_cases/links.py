"""Wikilink backlinks (document-links spec).

Backlinks are computed on demand: scan the workspace's documents' block text for
`[[<this document's title>]]`. Correct and index-free; O(workspace docs) per
view, so a persistent link index is a future optimization. Reuses the same CRDT
read path the agent uses (realtime.current_state -> engine.read_blocks).
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from cyberarche.application.authz import AccessControl
from cyberarche.application.kernel import CallerContext
from cyberarche.application.ports.crdt import CrdtEnginePort
from cyberarche.application.ports.inferred_links import (
    InferredLinkRecord,
    InferredLinkRepository,
    InferredRelation,
)
from cyberarche.application.ports.llm import LLMMessage, LLMPort
from cyberarche.application.ports.repositories import DocumentRepository
from cyberarche.application.ports.telemetry import ClockPort
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
    type: str = "links_to"  # links_to | depends_on | explains | cites | similar | …
    confidence: int = 100
    evidence: str = ""
    inferred: bool = False


@dataclass(frozen=True, slots=True)
class LinkGraph:
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class _EdgeAccumulator:
    """Collects graph edges, dropping self-links, links leaving the scope, and
    duplicates (keyed by source/target/type). Shared by the explicit and
    inferred graph builders so the dedup rule lives in one place."""

    def __init__(self, in_scope: set[str]) -> None:
        self._in_scope = in_scope
        self._seen: set[tuple[str, str, str]] = set()
        self.edges: list[GraphEdge] = []

    def add(self, edge: GraphEdge) -> None:
        key = (edge.source, edge.target, edge.type)
        if (
            edge.target
            and edge.target != edge.source
            and edge.target in self._in_scope
            and key not in self._seen
        ):
            self._seen.add(key)
            self.edges.append(edge)


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


_RELATION_TYPES = {
    "depends_on",
    "explains",
    "cites",
    "similar",
    "contradicts",
    "mentions",
}
_MIN_CONFIDENCE = 60
_MAX_INFER_DOCS = 40  # cap LLM calls per request; larger folders truncate


def _document_text(blocks: list[dict]) -> str:
    parts: list[str] = []
    for block in blocks:
        parts.extend(_block_texts(block))
    return "\n".join(t for t in parts if t.strip())


_INFER_SYSTEM = (
    "You classify how one document relates to others in a knowledge base. "
    "Given a source document and a list of other document titles, output only the "
    "OTHER documents the source has a meaningful relationship to. Relationship "
    "types: depends_on (the source needs it as a prerequisite), explains (the "
    "source expands or explains it), cites (the source references it as a source), "
    "similar (same topic/overlapping content), contradicts (conflicting claims), "
    "mentions (referenced in passing). Reply ONLY with a JSON array of objects "
    '{"target": "<exact other title>", "type": "<type>", "confidence": <0-100>, '
    '"evidence": "<short reason or quote>"}. Include a relationship only when '
    "confidence >= 60. If there are none, reply with []."
)


def _parse_relations(text: str, valid_titles: set[str]) -> tuple[InferredRelation, ...]:
    """Parse the model's JSON array, keeping only well-typed, confident relations
    whose target is a real other document."""
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end <= start:
        return ()
    try:
        items = json.loads(text[start : end + 1])
    except (ValueError, TypeError):
        return ()
    relations: list[InferredRelation] = []
    seen: set[tuple[str, str]] = set()
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        target = str(item.get("target", "")).strip()
        rel_type = str(item.get("type", "")).strip()
        try:
            confidence = int(item.get("confidence", 0))
        except (ValueError, TypeError):
            confidence = 0
        if (
            rel_type not in _RELATION_TYPES
            or confidence < _MIN_CONFIDENCE
            or target.lower() not in valid_titles
            or (target.lower(), rel_type) in seen
        ):
            continue
        seen.add((target.lower(), rel_type))
        relations.append(
            InferredRelation(
                target_title=target,
                type=rel_type,
                confidence=min(confidence, 100),
                evidence=str(item.get("evidence", ""))[:280],
            )
        )
    return tuple(relations)


class LinksUseCases:
    def __init__(
        self,
        documents: DocumentRepository,
        realtime: RealtimeUseCases,
        engine: CrdtEnginePort,
        access: AccessControl,
        llm: LLMPort | None = None,
        inferred_links: InferredLinkRepository | None = None,
        clock: ClockPort | None = None,
    ) -> None:
        self._documents = documents
        self._realtime = realtime
        self._engine = engine
        self._access = access
        self._llm = llm
        self._inferred = inferred_links
        self._clock = clock

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
        visible = await self._visible_documents(
            caller, teamspace_id=teamspace_id, folder_id=folder_id
        )
        if not visible:
            return LinkGraph(nodes=[], edges=[])
        title_to_id = await self._title_index(caller, visible[0].workspace_id)
        acc = _EdgeAccumulator({str(doc.id) for doc in visible})
        for doc in visible:
            source = str(doc.id)
            try:
                state = await self._realtime.current_state(caller, doc.id)
            except NotAuthorized:
                continue
            for title in _outgoing_titles(self._engine.read_blocks(state)):
                target = title_to_id.get(title)
                if target:
                    acc.add(GraphEdge(source=source, target=target))
        nodes = [GraphNode(id=str(doc.id), title=doc.title) for doc in visible]
        return LinkGraph(nodes=nodes, edges=acc.edges)

    async def _resolve_scope(
        self,
        caller: CallerContext,
        *,
        teamspace_id: TeamspaceId | None,
        folder_id: FolderId | None,
    ) -> list[Document]:
        if teamspace_id is not None:
            return await self._documents.list_for_teamspace(
                caller.tenant_id, teamspace_id
            )
        if folder_id is not None:
            return await self._documents.list_for_folder(caller.tenant_id, folder_id)
        raise ValidationFailed("teamspace_id or folder_id required")

    async def _visible_documents(
        self,
        caller: CallerContext,
        *,
        teamspace_id: TeamspaceId | None,
        folder_id: FolderId | None,
    ) -> list[Document]:
        """In-scope, non-trashed documents the caller may view."""
        scope = await self._resolve_scope(
            caller, teamspace_id=teamspace_id, folder_id=folder_id
        )
        visible: list[Document] = []
        for doc in scope:
            if not doc.trashed and await self._access.document_role(caller, doc) is not None:
                visible.append(doc)
        return visible

    async def _title_index(
        self, caller: CallerContext, workspace_id: str
    ) -> dict[str, str]:
        """Title -> id resolution across the workspace (same rule as wikilinks)."""
        index: dict[str, str] = {}
        for doc in await self._documents.list_in_workspace(caller.tenant_id, workspace_id):
            key = doc.title.strip().lower()
            if key and key not in index:
                index[key] = str(doc.id)
        return index

    async def inferred_graph(
        self,
        caller: CallerContext,
        *,
        teamspace_id: TeamspaceId | None = None,
        folder_id: FolderId | None = None,
    ) -> LinkGraph:
        """The graph with AI-inferred typed edges added to the explicit `[[…]]`
        edges. Inference is cached per document by content hash — a document is
        re-classified only when its content changed, so re-opening the view makes
        no LLM calls."""
        if self._inferred is None or self._llm is None or self._clock is None:
            return await self.graph(
                caller, teamspace_id=teamspace_id, folder_id=folder_id
            )
        visible = await self._visible_documents(
            caller, teamspace_id=teamspace_id, folder_id=folder_id
        )
        if not visible:
            return LinkGraph(nodes=[], edges=[])

        texts, explicit = await self._read_texts_and_links(caller, visible)
        title_to_id = await self._title_index(caller, visible[0].workspace_id)
        acc = _EdgeAccumulator({str(doc.id) for doc in visible})

        # Explicit `[[links]]`.
        for doc in visible:
            source = str(doc.id)
            for title in explicit.get(source, set()):
                target = title_to_id.get(title)
                if target:
                    acc.add(GraphEdge(source=source, target=target))

        await self._add_inferred_edges(caller, visible, texts, title_to_id, acc)

        nodes = [GraphNode(id=str(doc.id), title=doc.title) for doc in visible]
        return LinkGraph(nodes=nodes, edges=acc.edges)

    async def _read_texts_and_links(
        self, caller: CallerContext, visible: list[Document]
    ) -> tuple[dict[str, str], dict[str, set[str]]]:
        """Per-document plain text (for classification) and explicit `[[links]]`."""
        texts: dict[str, str] = {}
        explicit: dict[str, set[str]] = {}
        for doc in visible:
            try:
                blocks = self._engine.read_blocks(
                    await self._realtime.current_state(caller, doc.id)
                )
            except NotAuthorized:
                continue
            texts[str(doc.id)] = _document_text(blocks)
            explicit[str(doc.id)] = _outgoing_titles(blocks)
        return texts, explicit

    async def _inferred_relations(
        self,
        caller: CallerContext,
        doc: Document,
        text: str,
        visible: list[Document],
        cached: dict,
        classified: int,
    ) -> tuple[tuple[InferredRelation, ...], bool]:
        """Relations for one document: a fresh cache hit, or classify+cache when
        under the per-request cap. Returns (relations, did_classify)."""
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        record = cached.get(str(doc.id))
        if record is not None and record.content_hash == content_hash:
            return record.relations, False
        if classified >= _MAX_INFER_DOCS:
            return (), False  # over the cap; classified on a later request
        relations = await self._classify(doc, text, visible)
        await self._inferred.put(
            caller.tenant_id,
            InferredLinkRecord(
                source_document_id=str(doc.id),
                content_hash=content_hash,
                computed_at=self._clock.now(),
                relations=relations,
            ),
        )
        return relations, True

    async def _add_inferred_edges(
        self,
        caller: CallerContext,
        visible: list[Document],
        texts: dict[str, str],
        title_to_id: dict[str, str],
        acc: _EdgeAccumulator,
    ) -> None:
        """Add AI-inferred typed edges (cache hit, or classify + cache)."""
        cached = await self._inferred.get_many(
            caller.tenant_id, [doc.id for doc in visible]
        )
        classified = 0
        for doc in visible:
            relations, did_classify = await self._inferred_relations(
                caller, doc, texts.get(str(doc.id), ""), visible, cached, classified
            )
            if did_classify:
                classified += 1
            for rel in relations:
                target = title_to_id.get(rel.target_title.strip().lower())
                if target:
                    acc.add(
                        GraphEdge(
                            source=str(doc.id),
                            target=target,
                            type=rel.type,
                            confidence=rel.confidence,
                            evidence=rel.evidence,
                            inferred=True,
                        )
                    )

    async def _classify(
        self, doc: Document, text: str, others: list[Document]
    ) -> tuple[InferredRelation, ...]:
        """Ask the model how `doc` relates to the other in-scope documents."""
        candidates = [d for d in others if d.id != doc.id]
        if not candidates or not text.strip() or self._llm is None:
            return ()
        listing = "\n".join(f"- {d.title}" for d in candidates[:_MAX_INFER_DOCS])
        messages = [
            LLMMessage(role="system", content=_INFER_SYSTEM),
            LLMMessage(
                role="user",
                content=(
                    f'Document: "{doc.title}"\n{text[:1500]}\n\n'
                    f"Other documents in this folder:\n{listing}\n\n"
                    "Return the relationships as a JSON array."
                ),
            ),
        ]
        try:
            response = await self._llm.complete(messages, reasoning_effort="minimal")
        except Exception:
            return ()
        valid = {d.title.strip().lower() for d in candidates}
        return _parse_relations(response.text, valid)
