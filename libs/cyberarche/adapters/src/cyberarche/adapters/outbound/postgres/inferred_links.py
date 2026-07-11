"""InferredLinkRepository adapter over the document_inferred_links table."""

from __future__ import annotations

import json

import asyncpg

from cyberarche.application.ports.inferred_links import (
    InferredLinkRecord,
    InferredRelation,
)
from cyberarche.domain.ids import DocumentId, TenantId


def _record_from_row(row: asyncpg.Record) -> InferredLinkRecord:
    payload = row["payload"]
    if isinstance(payload, str):
        payload = json.loads(payload)
    relations = tuple(
        InferredRelation(
            target_title=str(item.get("target_title", "")),
            type=str(item.get("type", "")),
            confidence=int(item.get("confidence", 0)),
            evidence=str(item.get("evidence", "")),
        )
        for item in (payload or [])
    )
    return InferredLinkRecord(
        source_document_id=row["source_document_id"],
        content_hash=row["content_hash"],
        computed_at=row["computed_at"],
        relations=relations,
    )


class PostgresInferredLinkRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_many(
        self, tenant_id: TenantId, source_ids: list[DocumentId]
    ) -> dict[str, InferredLinkRecord]:
        if not source_ids:
            return {}
        rows = await self._pool.fetch(
            """
            SELECT source_document_id, content_hash, computed_at, payload
            FROM document_inferred_links
            WHERE tenant_id = $1 AND source_document_id = ANY($2::text[])
            """,
            tenant_id,
            [str(sid) for sid in source_ids],
        )
        return {row["source_document_id"]: _record_from_row(row) for row in rows}

    async def put(self, tenant_id: TenantId, record: InferredLinkRecord) -> None:
        payload = json.dumps(
            [
                {
                    "target_title": rel.target_title,
                    "type": rel.type,
                    "confidence": rel.confidence,
                    "evidence": rel.evidence,
                }
                for rel in record.relations
            ]
        )
        await self._pool.execute(
            """
            INSERT INTO document_inferred_links
                (source_document_id, tenant_id, content_hash, computed_at, payload)
            VALUES ($1, $2, $3, $4, $5::jsonb)
            ON CONFLICT (source_document_id) DO UPDATE
                SET tenant_id = EXCLUDED.tenant_id,
                    content_hash = EXCLUDED.content_hash,
                    computed_at = EXCLUDED.computed_at,
                    payload = EXCLUDED.payload
            """,
            record.source_document_id,
            tenant_id,
            record.content_hash,
            record.computed_at,
            payload,
        )
