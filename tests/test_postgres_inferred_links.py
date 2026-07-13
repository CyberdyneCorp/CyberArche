"""PostgresInferredLinkRepository wire-level behavior over a recording fake pool."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from cyberarche.adapters.outbound.postgres.inferred_links import (
    PostgresInferredLinkRepository,
)
from cyberarche.application.ports.inferred_links import (
    InferredLinkRecord,
    InferredRelation,
)
from cyberarche.domain.ids import DocumentId, TenantId

NOW = datetime(2026, 1, 1, tzinfo=UTC)


class FakePool:
    """Records (query, args) calls; returns canned rows for fetch."""

    def __init__(self, rows: list[dict] | None = None) -> None:
        self.rows = rows or []
        self.calls: list[tuple[str, tuple]] = []

    async def fetch(self, query: str, *args) -> list[dict]:
        self.calls.append((query, args))
        return self.rows

    async def execute(self, query: str, *args) -> str:
        self.calls.append((query, args))
        return "INSERT 0 1"


def row(source_id: str = "doc-1", payload=None, content_hash: str = "hash-1") -> dict:
    return {
        "source_document_id": source_id,
        "content_hash": content_hash,
        "computed_at": NOW,
        "payload": payload,
    }


async def test_get_many_returns_empty_without_querying_when_no_ids():
    pool = FakePool()
    repo = PostgresInferredLinkRepository(pool)

    assert await repo.get_many(TenantId("acme"), []) == {}
    assert pool.calls == []  # short-circuits before touching the pool


async def test_get_many_maps_rows_keyed_by_source_and_stringifies_ids():
    payload = [
        {
            "target_title": "Limits",
            "type": "depends_on",
            "confidence": 94,
            "evidence": "builds on limits",
        }
    ]
    pool = FakePool(rows=[row("doc-1", payload=payload)])
    repo = PostgresInferredLinkRepository(pool)

    out = await repo.get_many(TenantId("acme"), [DocumentId("doc-1"), DocumentId("doc-2")])

    assert set(out) == {"doc-1"}
    record = out["doc-1"]
    assert record.source_document_id == "doc-1"
    assert record.content_hash == "hash-1"
    assert record.computed_at == NOW
    assert record.relations == (
        InferredRelation(
            target_title="Limits",
            type="depends_on",
            confidence=94,
            evidence="builds on limits",
        ),
    )
    query, args = pool.calls[0]
    assert "document_inferred_links" in query
    assert args == ("acme", ["doc-1", "doc-2"])


async def test_get_many_parses_payload_delivered_as_json_string():
    payload = json.dumps(
        [{"target_title": "T", "type": "cites", "confidence": 50, "evidence": "e"}]
    )
    pool = FakePool(rows=[row(payload=payload)])
    repo = PostgresInferredLinkRepository(pool)

    out = await repo.get_many(TenantId("acme"), [DocumentId("doc-1")])
    assert out["doc-1"].relations == (
        InferredRelation(target_title="T", type="cites", confidence=50, evidence="e"),
    )


async def test_get_many_treats_null_payload_as_no_relations():
    pool = FakePool(rows=[row(payload=None)])
    repo = PostgresInferredLinkRepository(pool)

    out = await repo.get_many(TenantId("acme"), [DocumentId("doc-1")])
    assert out["doc-1"].relations == ()


async def test_get_many_defaults_missing_relation_fields():
    pool = FakePool(rows=[row(payload=[{}])])
    repo = PostgresInferredLinkRepository(pool)

    out = await repo.get_many(TenantId("acme"), [DocumentId("doc-1")])
    assert out["doc-1"].relations == (
        InferredRelation(target_title="", type="", confidence=0, evidence=""),
    )


async def test_get_many_coerces_relation_field_types():
    payload = [
        {"target_title": 7, "type": None, "confidence": "88", "evidence": 1.5}
    ]
    pool = FakePool(rows=[row(payload=payload)])
    repo = PostgresInferredLinkRepository(pool)

    out = await repo.get_many(TenantId("acme"), [DocumentId("doc-1")])
    rel = out["doc-1"].relations[0]
    assert rel == InferredRelation(
        target_title="7", type="None", confidence=88, evidence="1.5"
    )


async def test_put_upserts_record_with_json_payload():
    pool = FakePool()
    repo = PostgresInferredLinkRepository(pool)
    record = InferredLinkRecord(
        source_document_id="doc-1",
        content_hash="hash-9",
        computed_at=NOW,
        relations=(
            InferredRelation(
                target_title="Limits", type="explains", confidence=70, evidence="ev"
            ),
        ),
    )

    await repo.put(TenantId("acme"), record)

    query, args = pool.calls[0]
    assert "ON CONFLICT (source_document_id) DO UPDATE" in query
    assert args[:4] == ("doc-1", "acme", "hash-9", NOW)
    assert json.loads(args[4]) == [
        {
            "target_title": "Limits",
            "type": "explains",
            "confidence": 70,
            "evidence": "ev",
        }
    ]


async def test_put_with_no_relations_stores_empty_json_array():
    pool = FakePool()
    repo = PostgresInferredLinkRepository(pool)
    record = InferredLinkRecord(
        source_document_id="doc-1", content_hash="hash-0", computed_at=NOW
    )

    await repo.put(TenantId("acme"), record)

    _, args = pool.calls[0]
    assert args[4] == "[]"
