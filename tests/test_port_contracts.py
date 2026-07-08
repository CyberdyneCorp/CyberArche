"""architecture-quality 12.2/12.3: shared contract suites per port.

Every implementation of a port must pass the same behavioral contract.
Suites are parametrized by backend: "memory" always runs; "postgres" is
included when TEST_DATABASE_URL is set (integration environments), so new
adapters plug into the same assertions instead of ad-hoc tests.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest

from cyberarche.domain.documents import Document
from cyberarche.domain.ids import DocumentId, TeamspaceId, TenantId, UserId, WorkspaceId
from cyberarche.domain.workspaces import Workspace

BACKENDS = ["memory"] + (["postgres"] if os.environ.get("TEST_DATABASE_URL") else [])

NOW = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture(params=BACKENDS)
async def adapters(request):
    """Bundle of port implementations under contract test."""
    if request.param == "memory":
        from cyberarche.application.testing import fakes

        yield {
            "workspaces": fakes.InMemoryWorkspaceRepository(),
            "documents": fakes.InMemoryDocumentRepository(),
            "update_log": fakes.InMemoryUpdateLog(),
            "blobs": fakes.InMemoryBlobStorage(),
            "queue": fakes.InMemoryTaskQueue(),
            "api_keys": fakes.InMemoryApiKeyRepository(),
            "teamspaces": fakes.InMemoryTeamspaceRepository(),
            "favorites": fakes.InMemoryFavoriteRepository(),
        }
        return
    # postgres: real adapters over TEST_DATABASE_URL (integration runs)
    import asyncpg

    from cyberarche.adapters.outbound.postgres.repositories import (
        PostgresDocumentRepository,
        PostgresWorkspaceRepository,
    )
    from cyberarche.adapters.outbound.postgres.api_keys import PostgresApiKeyRepository
    from cyberarche.adapters.outbound.postgres.teamspaces import (
        PostgresFavoriteRepository,
        PostgresTeamspaceRepository,
    )
    from cyberarche.adapters.outbound.postgres.update_log import PostgresUpdateLog
    from cyberarche.application.testing import fakes

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"])
    try:
        # Isolate each test: the suite owns this database.
        await pool.execute(
            "TRUNCATE workspaces, documents, snapshots, crdt_updates, "
            "workspace_memberships, document_grants, share_links, agent_runs, "
            "mcp_connectors, ingestion_tasks, comments, api_keys, "
            "teamspaces, teamspace_memberships, favorites CASCADE"
        )
        yield {
            "workspaces": PostgresWorkspaceRepository(pool),
            "documents": PostgresDocumentRepository(pool),
            "update_log": PostgresUpdateLog(pool),
            "blobs": fakes.InMemoryBlobStorage(),
            "queue": fakes.InMemoryTaskQueue(),
            "api_keys": PostgresApiKeyRepository(pool),
            "teamspaces": PostgresTeamspaceRepository(pool),
            "favorites": PostgresFavoriteRepository(pool),
        }
    finally:
        await pool.close()


def workspace(workspace_id="ws-1", tenant="acme") -> Workspace:
    return Workspace(
        id=WorkspaceId(workspace_id),
        tenant_id=TenantId(tenant),
        name="WS",
        created_by=UserId("alice"),
        created_at=NOW,
    )


def document(document_id="doc-1", workspace_id="ws-1", tenant="acme", **kw) -> Document:
    return Document.create(
        id=DocumentId(document_id),
        workspace_id=WorkspaceId(workspace_id),
        tenant_id=TenantId(tenant),
        title=kw.get("title", "Doc"),
        parent_id=kw.get("parent_id"),
        position=kw.get("position", 0),
        created_by=UserId("alice"),
        created_at=NOW,
    )


async def test_workspace_repository_contract(adapters):
    repo = adapters["workspaces"]
    await repo.add(workspace())

    assert (await repo.get(TenantId("acme"), WorkspaceId("ws-1"))) is not None
    assert (await repo.get(TenantId("globex"), WorkspaceId("ws-1"))) is None
    assert [w.id for w in await repo.list_for_tenant(TenantId("acme"))] == ["ws-1"]

    renamed = workspace().rename("Renamed").with_rag_project("slug-1")
    await repo.update(renamed)
    fetched = await repo.get(TenantId("acme"), WorkspaceId("ws-1"))
    assert fetched.name == "Renamed" and fetched.rag_project_slug == "slug-1"


async def test_document_repository_contract(adapters):
    ws_repo, repo = adapters["workspaces"], adapters["documents"]
    await ws_repo.add(workspace())
    await repo.add(document("d-1", title="Alpha Plan", position=1))
    await repo.add(document("d-2", title="beta plan", position=0))

    tenant = TenantId("acme")
    assert (await repo.get(tenant, DocumentId("d-1"))).title == "Alpha Plan"
    assert (await repo.get(TenantId("globex"), DocumentId("d-1"))) is None
    assert (await repo.get_any_tenant(DocumentId("d-1"))) is not None

    ordered = await repo.children(tenant, WorkspaceId("ws-1"), None)
    assert [d.id for d in ordered] == ["d-2", "d-1"]  # by position

    found = await repo.search_by_title(tenant, "plan")
    assert sorted(d.id for d in found) == ["d-1", "d-2"]  # case-insensitive

    trashed = (await repo.get(tenant, DocumentId("d-1"))).trash(now=NOW)
    await repo.update(trashed)
    assert [d.id for d in await repo.list_trashed(tenant, WorkspaceId("ws-1"))] == ["d-1"]
    assert [d.id for d in await repo.children(tenant, WorkspaceId("ws-1"), None)] == ["d-2"]
    assert await repo.search_by_title(tenant, "alpha") == []  # trashed excluded


async def test_update_log_contract(adapters):
    ws_repo, doc_repo, log = adapters["workspaces"], adapters["documents"], adapters["update_log"]
    await ws_repo.add(workspace())
    await doc_repo.add(document("d-1"))
    doc = DocumentId("d-1")

    first = await log.append(doc, b"u1", origin="alice")
    second = await log.append(doc, b"u2", origin="agent:alice")
    assert second.seq > first.seq
    assert await log.count(doc) == 2
    assert [u.update for u in await log.list_for_document(doc)] == [b"u1", b"u2"]

    await log.replace_with(doc, b"merged", up_to_seq=second.seq)
    remaining = await log.list_for_document(doc)
    assert [u.update for u in remaining] == [b"merged"]
    assert remaining[0].origin == "compaction"


async def test_blob_storage_contract(adapters):
    blobs = adapters["blobs"]
    await blobs.put("a/b/file.txt", b"content", content_type="text/plain")

    blob = await blobs.get("a/b/file.txt")
    assert blob.content == b"content" and blob.content_type == "text/plain"
    assert await blobs.get("missing") is None

    await blobs.delete("a/b/file.txt")
    assert await blobs.get("a/b/file.txt") is None
    await blobs.delete("a/b/file.txt")  # idempotent


async def test_task_queue_contract(adapters):
    queue = adapters["queue"]
    job_id = await queue.enqueue("test.job", {"n": 1})
    assert job_id

    job = await queue.dequeue(timeout=0.1)
    assert job.type == "test.job" and job.payload == {"n": 1} and job.id == job_id
    assert await queue.dequeue(timeout=0.05) is None  # empty -> None, no raise


async def test_filesystem_blob_adapter_passes_the_same_contract(tmp_path):
    """The filesystem adapter honors the identical blob contract."""
    from cyberarche.adapters.outbound.objectstore.filesystem import (
        FilesystemBlobStorage,
    )

    blobs = FilesystemBlobStorage(tmp_path)
    await blobs.put("ingest/ws/hash/report final.pdf", b"%PDF", content_type="application/pdf")
    blob = await blobs.get("ingest/ws/hash/report final.pdf")
    assert blob.content == b"%PDF" and blob.content_type == "application/pdf"
    assert await blobs.get("nope") is None
    await blobs.delete("ingest/ws/hash/report final.pdf")
    assert await blobs.get("ingest/ws/hash/report final.pdf") is None


async def test_api_key_repository_contract(adapters):
    from cyberarche.domain.api_keys import ApiKey

    repo = adapters["api_keys"]
    key = ApiKey(
        id="k-1",
        tenant_id=TenantId("acme"),
        user_id=UserId("alice"),
        name="Claude",
        secret_hash="hash-1",
        prefix="cak_abcd1234…",
        created_at=NOW,
    )
    await repo.add(key)

    assert (await repo.by_hash("hash-1")).id == "k-1"
    assert await repo.by_hash("nope") is None
    assert (await repo.get(UserId("alice"), "k-1")) is not None
    assert await repo.get(UserId("mallory"), "k-1") is None
    assert [k.id for k in await repo.list_for_user(TenantId("acme"), UserId("alice"))] == ["k-1"]

    await repo.update(key.revoke(NOW).touched(NOW))
    stored = await repo.by_hash("hash-1")
    assert stored.revoked_at == NOW and stored.last_used_at == NOW


async def test_teamspace_repository_contract(adapters):
    from cyberarche.domain.memberships import Role
    from cyberarche.domain.teamspaces import Teamspace, TeamspaceMembership

    ws_repo, repo = adapters["workspaces"], adapters["teamspaces"]
    await ws_repo.add(workspace())
    teamspace = Teamspace(
        id=TeamspaceId("ts-1"), workspace_id=WorkspaceId("ws-1"),
        tenant_id=TenantId("acme"), name="Tessera", icon="T",
        created_by=UserId("alice"), created_at=NOW,
    )
    await repo.add(teamspace)

    assert (await repo.get(TenantId("acme"), TeamspaceId("ts-1"))).name == "Tessera"
    assert await repo.get(TenantId("globex"), TeamspaceId("ts-1")) is None
    assert [t.id for t in await repo.list_for_workspace(TenantId("acme"), WorkspaceId("ws-1"))] == ["ts-1"]

    await repo.add_member(TeamspaceMembership(
        teamspace_id=TeamspaceId("ts-1"), user_id=UserId("bob"),
        role=Role.EDITOR, granted_at=NOW))
    assert (await repo.member_role(TeamspaceId("ts-1"), UserId("bob"))).role is Role.EDITOR
    assert await repo.member_role(TeamspaceId("ts-1"), UserId("carol")) is None
    assert [m.user_id for m in await repo.members(TeamspaceId("ts-1"))] == ["bob"]
    mine = await repo.teamspaces_for_user(TenantId("acme"), WorkspaceId("ws-1"), UserId("bob"))
    assert [t.id for t in mine] == ["ts-1"]

    await repo.remove_member(TeamspaceId("ts-1"), UserId("bob"))
    assert await repo.member_role(TeamspaceId("ts-1"), UserId("bob")) is None


async def test_document_teamspace_listing_contract(adapters):
    ws_repo, doc_repo, ts_repo = adapters["workspaces"], adapters["documents"], adapters["teamspaces"]
    from cyberarche.domain.teamspaces import Teamspace

    await ws_repo.add(workspace())
    await ts_repo.add(Teamspace(
        id=TeamspaceId("ts-1"), workspace_id=WorkspaceId("ws-1"),
        tenant_id=TenantId("acme"), name="T", icon="T",
        created_by=UserId("alice"), created_at=NOW))
    inside = document("d-1")
    from dataclasses import replace
    await doc_repo.add(replace(inside, teamspace_id=TeamspaceId("ts-1")))
    await doc_repo.add(document("d-2"))  # workspace-level

    listed = await doc_repo.list_for_teamspace(TenantId("acme"), TeamspaceId("ts-1"))
    assert [d.id for d in listed] == ["d-1"]
    assert (await doc_repo.get(TenantId("acme"), DocumentId("d-1"))).teamspace_id == "ts-1"
    assert (await doc_repo.get(TenantId("acme"), DocumentId("d-2"))).teamspace_id is None

    # update() must persist teamspace_id too (moving a document into a teamspace).
    moved = replace(await doc_repo.get(TenantId("acme"), DocumentId("d-2")),
                    teamspace_id=TeamspaceId("ts-1"))
    await doc_repo.update(moved)
    assert (await doc_repo.get(TenantId("acme"), DocumentId("d-2"))).teamspace_id == "ts-1"
    assert len(await doc_repo.list_for_teamspace(TenantId("acme"), TeamspaceId("ts-1"))) == 2


async def test_favorite_repository_contract(adapters):
    ws_repo, doc_repo, repo = adapters["workspaces"], adapters["documents"], adapters["favorites"]
    await ws_repo.add(workspace())
    await doc_repo.add(document("d-1"))

    await repo.add(UserId("alice"), DocumentId("d-1"))
    await repo.add(UserId("alice"), DocumentId("d-1"))  # idempotent
    assert await repo.list_for_user(UserId("alice")) == ["d-1"]
    assert await repo.is_favorite(UserId("alice"), DocumentId("d-1"))
    assert await repo.list_for_user(UserId("bob")) == []  # per user

    await repo.remove(UserId("alice"), DocumentId("d-1"))
    assert await repo.list_for_user(UserId("alice")) == []
