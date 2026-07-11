"""Inferred-links cache port (ai-inferred-links spec).

Caches the LLM-inferred typed relationships for a document, keyed by a hash of
that document's content, so the graph explorer can show inferred edges without
re-asking the model on every open. A record is stale (and re-classified) only
when its `content_hash` no longer matches the document's current content.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from cyberarche.domain.ids import DocumentId, TenantId


@dataclass(frozen=True, slots=True)
class InferredRelation:
    """One inferred relationship from a source document to another, by title."""

    target_title: str
    type: str  # depends_on | explains | cites | similar | contradicts | mentions
    confidence: int  # 0..100
    evidence: str


@dataclass(frozen=True, slots=True)
class InferredLinkRecord:
    source_document_id: str
    content_hash: str
    computed_at: datetime
    relations: tuple[InferredRelation, ...] = field(default_factory=tuple)


class InferredLinkRepository(Protocol):
    async def get_many(
        self, tenant_id: TenantId, source_ids: list[DocumentId]
    ) -> dict[str, InferredLinkRecord]:
        """Cached records for the given source documents (missing ids omitted)."""
        ...

    async def put(self, tenant_id: TenantId, record: InferredLinkRecord) -> None:
        """Upsert a document's inferred relationships (replacing any prior row)."""
        ...
