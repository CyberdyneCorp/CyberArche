"""Unit tests for the asyncpg-backed repositories (postgres/repositories.py).

The adapters are thin row<->aggregate mappers; these tests stub the asyncpg
pool directly and assert the SQL shape, the bound parameters (tenant scoping
included), and both directions of the row mapping — success, miss (None),
and every optional-column branch. The behavioral contract against a real
database lives in test_port_contracts.py.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from cyberarche.adapters.outbound.postgres.repositories import (
    PostgresDocumentRepository,
    PostgresMembershipRepository,
    PostgresSnapshotRepository,
    PostgresWorkspaceRepository,
)
from cyberarche.domain.documents import Document
from cyberarche.domain.errors import NotFound
from cyberarche.domain.ids import (
    DocumentId,
    FolderId,
    SnapshotId,
    TeamspaceId,
    TenantId,
    UserId,
    WorkspaceId,
)
from cyberarche.domain.memberships import DocumentGrant, Role, WorkspaceMembership
from cyberarche.domain.snapshots import Snapshot
from cyberarche.domain.workspaces import Workspace

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _squash(sql: str) -> str:
    return " ".join(sql.split())


class _Transaction:
    def __init__(self, pool: "FakePool") -> None:
        self._pool = pool

    async def __aenter__(self) -> None:
        self._pool.transactions += 1

    async def __aexit__(self, *exc_info: object) -> bool:
        return False


class _Connection:
    def __init__(self, pool: "FakePool") -> None:
        self._pool = pool

    def transaction(self) -> _Transaction:
        return _Transaction(self._pool)

    async def fetch(self, query: str, *args: object) -> list:
        return await self._pool.fetch(query, *args)

    async def execute(self, query: str, *args: object) -> None:
        await self._pool.execute(query, *args)


class _Acquire:
    def __init__(self, pool: "FakePool") -> None:
        self._pool = pool

    async def __aenter__(self) -> _Connection:
        return _Connection(self._pool)

    async def __aexit__(self, *exc_info: object) -> bool:
        return False


class FakePool:
    """Stands in for asyncpg.Pool: records queries, replays canned rows."""

    def __init__(self, *, rows: list | None = None, row: dict | None = None) -> None:
        self.rows = rows or []
        self.row = row
        self.calls: list[tuple[str, tuple]] = []
        self.transactions = 0

    async def execute(self, query: str, *args: object) -> None:
        self.calls.append((_squash(query), args))

    async def fetch(self, query: str, *args: object) -> list:
        self.calls.append((_squash(query), args))
        return self.rows

    async def fetchrow(self, query: str, *args: object) -> dict | None:
        self.calls.append((_squash(query), args))
        return self.row

    def acquire(self) -> _Acquire:
        return _Acquire(self)


def workspace_row(**overrides: object) -> dict:
    row = {
        "id": "ws-1",
        "tenant_id": "acme",
        "name": "WS",
        "created_by": "alice",
        "created_at": NOW,
        "rag_project_slug": None,
    }
    row.update(overrides)
    return row


def document_row(**overrides: object) -> dict:
    row = {
        "id": "d-1",
        "workspace_id": "ws-1",
        "tenant_id": "acme",
        "title": "Doc",
        "parent_id": None,
        "position": 0,
        "created_by": "alice",
        "created_at": NOW,
        "updated_at": NOW,
        "trashed": False,
        "trashed_from_parent_id": None,
        "teamspace_id": None,
        "folder_id": None,
    }
    row.update(overrides)
    return row


def snapshot_row(**overrides: object) -> dict:
    row = {
        "id": "s-1",
        "document_id": "d-1",
        "seq": 1,
        "content": json.dumps({"blocks": []}),
        "state_vector": b"\x01\x02",
        "created_at": NOW,
        "restored_from": None,
        "created_by": None,
        "label": None,
    }
    row.update(overrides)
    return row


def make_workspace(**overrides: object) -> Workspace:
    fields: dict = dict(
        id=WorkspaceId("ws-1"),
        tenant_id=TenantId("acme"),
        name="WS",
        created_by=UserId("alice"),
        created_at=NOW,
        rag_project_slug="slug-1",
    )
    fields.update(overrides)
    return Workspace(**fields)


def make_document(**overrides: object) -> Document:
    fields: dict = dict(
        id=DocumentId("d-1"),
        workspace_id=WorkspaceId("ws-1"),
        tenant_id=TenantId("acme"),
        title="Doc",
        parent_id=None,
        position=0,
        created_by=UserId("alice"),
        created_at=NOW,
        updated_at=NOW,
    )
    fields.update(overrides)
    return Document(**fields)


# --- PostgresWorkspaceRepository -------------------------------------------


async def test_workspace_add_binds_every_column():
    pool = FakePool()
    await PostgresWorkspaceRepository(pool).add(make_workspace())

    query, args = pool.calls[0]
    assert query.startswith("INSERT INTO workspaces")
    assert args == ("ws-1", "acme", "WS", "alice", NOW, "slug-1")


async def test_workspace_get_maps_row_and_scopes_by_tenant():
    pool = FakePool(row=workspace_row(rag_project_slug="slug-1"))
    found = await PostgresWorkspaceRepository(pool).get(
        TenantId("acme"), WorkspaceId("ws-1")
    )

    assert found == make_workspace()
    _, args = pool.calls[0]
    assert args == ("ws-1", "acme")


async def test_workspace_get_returns_none_when_missing():
    pool = FakePool(row=None)
    repo = PostgresWorkspaceRepository(pool)
    assert await repo.get(TenantId("acme"), WorkspaceId("nope")) is None


async def test_workspace_list_for_tenant_maps_rows():
    pool = FakePool(rows=[workspace_row(), workspace_row(id="ws-2", name="Two")])
    listed = await PostgresWorkspaceRepository(pool).list_for_tenant(TenantId("acme"))

    assert [w.id for w in listed] == ["ws-1", "ws-2"]
    assert listed[0].rag_project_slug is None
    _, args = pool.calls[0]
    assert args == ("acme",)


async def test_workspace_update_binds_name_and_slug():
    pool = FakePool()
    await PostgresWorkspaceRepository(pool).update(make_workspace(name="Renamed"))

    query, args = pool.calls[0]
    assert query.startswith("UPDATE workspaces")
    assert args == ("ws-1", "Renamed", "slug-1")


# --- PostgresDocumentRepository ---------------------------------------------


async def test_document_add_binds_all_thirteen_columns():
    pool = FakePool()
    document = make_document(
        parent_id=DocumentId("p-1"),
        teamspace_id=TeamspaceId("ts-1"),
        folder_id=FolderId("f-1"),
    )
    await PostgresDocumentRepository(pool).add(document)

    query, args = pool.calls[0]
    assert query.startswith("INSERT INTO documents")
    assert args == (
        "d-1", "ws-1", "acme", "Doc", "p-1", 0,
        "alice", NOW, NOW, False, None, "ts-1", "f-1",
    )


async def test_document_get_maps_optional_columns_when_null():
    pool = FakePool(row=document_row())
    found = await PostgresDocumentRepository(pool).get(
        TenantId("acme"), DocumentId("d-1")
    )

    assert found == make_document()
    assert found.parent_id is None
    assert found.trashed_from_parent_id is None
    assert found.teamspace_id is None
    assert found.folder_id is None
    _, args = pool.calls[0]
    assert args == ("d-1", "acme")


async def test_document_get_maps_optional_columns_when_set():
    pool = FakePool(
        row=document_row(
            parent_id="p-1",
            trashed=True,
            trashed_from_parent_id="p-1",
            teamspace_id="ts-1",
            folder_id="f-1",
        )
    )
    found = await PostgresDocumentRepository(pool).get(
        TenantId("acme"), DocumentId("d-1")
    )

    assert found.parent_id == DocumentId("p-1")
    assert found.trashed is True
    assert found.trashed_from_parent_id == DocumentId("p-1")
    assert found.teamspace_id == TeamspaceId("ts-1")
    assert found.folder_id == FolderId("f-1")


async def test_document_get_returns_none_when_missing():
    pool = FakePool(row=None)
    repo = PostgresDocumentRepository(pool)
    assert await repo.get(TenantId("acme"), DocumentId("nope")) is None


async def test_document_get_any_tenant_maps_row_without_tenant_filter():
    pool = FakePool(row=document_row())
    found = await PostgresDocumentRepository(pool).get_any_tenant(DocumentId("d-1"))

    assert found == make_document()
    query, args = pool.calls[0]
    assert "tenant_id" not in query
    assert args == ("d-1",)


async def test_document_get_any_tenant_returns_none_when_missing():
    pool = FakePool(row=None)
    repo = PostgresDocumentRepository(pool)
    assert await repo.get_any_tenant(DocumentId("nope")) is None


async def test_document_children_defaults_to_excluding_trashed():
    pool = FakePool(rows=[document_row()])
    children = await PostgresDocumentRepository(pool).children(
        TenantId("acme"), WorkspaceId("ws-1"), None
    )

    assert [d.id for d in children] == ["d-1"]
    _, args = pool.calls[0]
    assert args == ("acme", "ws-1", None, False)


async def test_document_children_can_include_trashed_under_a_parent():
    pool = FakePool(rows=[])
    await PostgresDocumentRepository(pool).children(
        TenantId("acme"), WorkspaceId("ws-1"), DocumentId("p-1"), include_trashed=True
    )

    _, args = pool.calls[0]
    assert args == ("acme", "ws-1", "p-1", True)


async def test_document_list_trashed_scopes_by_tenant_and_workspace():
    pool = FakePool(rows=[document_row(trashed=True, trashed_from_parent_id="p-1")])
    trashed = await PostgresDocumentRepository(pool).list_trashed(
        TenantId("acme"), WorkspaceId("ws-1")
    )

    assert trashed[0].trashed is True
    query, args = pool.calls[0]
    assert "trashed = TRUE" in query
    assert args == ("acme", "ws-1")


async def test_document_list_in_workspace_maps_rows():
    pool = FakePool(rows=[document_row(), document_row(id="d-2")])
    listed = await PostgresDocumentRepository(pool).list_in_workspace(
        TenantId("acme"), WorkspaceId("ws-1")
    )

    assert [d.id for d in listed] == ["d-1", "d-2"]
    _, args = pool.calls[0]
    assert args == ("acme", "ws-1")


async def test_document_list_for_teamspace_binds_teamspace_id():
    pool = FakePool(rows=[document_row(teamspace_id="ts-1")])
    listed = await PostgresDocumentRepository(pool).list_for_teamspace(
        TenantId("acme"), TeamspaceId("ts-1")
    )

    assert listed[0].teamspace_id == TeamspaceId("ts-1")
    _, args = pool.calls[0]
    assert args == ("acme", "ts-1")


async def test_document_list_for_folder_binds_folder_id():
    pool = FakePool(rows=[document_row(folder_id="f-1")])
    listed = await PostgresDocumentRepository(pool).list_for_folder(
        TenantId("acme"), FolderId("f-1")
    )

    assert listed[0].folder_id == FolderId("f-1")
    _, args = pool.calls[0]
    assert args == ("acme", "f-1")


async def test_document_update_binds_the_mutable_columns():
    pool = FakePool()
    document = make_document(
        title="Renamed",
        parent_id=DocumentId("p-1"),
        position=3,
        trashed=True,
        trashed_from_parent_id=DocumentId("p-1"),
        teamspace_id=TeamspaceId("ts-1"),
        folder_id=FolderId("f-1"),
    )
    await PostgresDocumentRepository(pool).update(document)

    query, args = pool.calls[0]
    assert query.startswith("UPDATE documents SET")
    assert args == ("d-1", "Renamed", "p-1", 3, NOW, True, "p-1", "ts-1", "f-1")


async def test_document_search_by_title_uses_default_limit():
    pool = FakePool(rows=[document_row(title="Alpha Plan")])
    found = await PostgresDocumentRepository(pool).search_by_title(
        TenantId("acme"), "plan"
    )

    assert [d.title for d in found] == ["Alpha Plan"]
    _, args = pool.calls[0]
    assert args == ("acme", "plan", 20)


async def test_document_search_by_title_honors_custom_limit():
    pool = FakePool(rows=[])
    await PostgresDocumentRepository(pool).search_by_title(
        TenantId("acme"), "plan", limit=5
    )

    _, args = pool.calls[0]
    assert args == ("acme", "plan", 5)


async def test_document_update_many_updates_each_inside_one_transaction():
    pool = FakePool()
    documents = [make_document(), make_document(id=DocumentId("d-2"), position=1)]
    await PostgresDocumentRepository(pool).update_many(documents)

    assert pool.transactions == 1
    assert len(pool.calls) == 2
    assert all(query.startswith("UPDATE documents SET") for query, _ in pool.calls)
    assert pool.calls[0][1][0] == "d-1"
    assert pool.calls[1][1][0] == "d-2"


async def test_document_purge_deletes_root_and_reports_the_subtree():
    pool = FakePool(rows=[{"id": "p-1"}, {"id": "c-1"}])
    purged = await PostgresDocumentRepository(pool).purge(
        TenantId("acme"), DocumentId("p-1")
    )

    assert purged == [DocumentId("p-1"), DocumentId("c-1")]
    assert pool.transactions == 1
    select_query, select_args = pool.calls[0]
    assert "WITH RECURSIVE subtree" in select_query
    assert select_args == ("p-1", "acme")
    delete_query, delete_args = pool.calls[1]
    assert delete_query.startswith("DELETE FROM documents")
    assert delete_args == ("p-1", "acme")


async def test_document_purge_of_missing_document_is_a_noop():
    pool = FakePool(rows=[])
    purged = await PostgresDocumentRepository(pool).purge(
        TenantId("acme"), DocumentId("gone")
    )

    assert purged == []
    # Only the subtree SELECT ran; no DELETE was issued.
    assert len(pool.calls) == 1
    assert "WITH RECURSIVE subtree" in pool.calls[0][0]


# --- PostgresSnapshotRepository ---------------------------------------------


async def test_snapshot_add_serializes_content_to_json():
    pool = FakePool()
    snapshot = Snapshot(
        id=SnapshotId("s-1"),
        document_id=DocumentId("d-1"),
        seq=1,
        content={"blocks": [{"id": "b1"}]},
        state_vector=b"\x01\x02",
        created_at=NOW,
        restored_from=SnapshotId("s-0"),
        created_by=UserId("alice"),
        label="Milestone",
    )
    await PostgresSnapshotRepository(pool).add(snapshot)

    query, args = pool.calls[0]
    assert query.startswith("INSERT INTO snapshots")
    assert args == (
        "s-1", "d-1", 1, json.dumps({"blocks": [{"id": "b1"}]}),
        b"\x01\x02", NOW, "s-0", "alice", "Milestone",
    )


async def test_snapshot_set_label_updates_and_maps_the_row():
    pool = FakePool(row=snapshot_row(label="Reviewed"))
    updated = await PostgresSnapshotRepository(pool).set_label(
        DocumentId("d-1"), SnapshotId("s-1"), "Reviewed"
    )

    assert updated.label == "Reviewed"
    query, args = pool.calls[0]
    assert query.startswith("UPDATE snapshots SET label")
    assert args == ("s-1", "d-1", "Reviewed")


async def test_snapshot_set_label_raises_when_missing():
    pool = FakePool(row=None)
    with pytest.raises(NotFound):
        await PostgresSnapshotRepository(pool).set_label(
            DocumentId("d-1"), SnapshotId("nope"), "x"
        )


async def test_snapshot_get_maps_row_with_optional_columns_set():
    pool = FakePool(
        row=snapshot_row(
            content=json.dumps({"blocks": [1]}),
            state_vector=bytearray(b"\xff"),
            restored_from="s-0",
            created_by="alice",
        )
    )
    found = await PostgresSnapshotRepository(pool).get(
        DocumentId("d-1"), SnapshotId("s-1")
    )

    assert found.content == {"blocks": [1]}
    assert found.state_vector == b"\xff"
    assert found.restored_from == SnapshotId("s-0")
    assert found.created_by == UserId("alice")
    _, args = pool.calls[0]
    assert args == ("s-1", "d-1")


async def test_snapshot_get_returns_none_when_missing():
    pool = FakePool(row=None)
    repo = PostgresSnapshotRepository(pool)
    assert await repo.get(DocumentId("d-1"), SnapshotId("nope")) is None


async def test_snapshot_list_for_document_maps_rows():
    pool = FakePool(rows=[snapshot_row(), snapshot_row(id="s-2", seq=2)])
    listed = await PostgresSnapshotRepository(pool).list_for_document(
        DocumentId("d-1")
    )

    assert [(s.id, s.seq) for s in listed] == [("s-1", 1), ("s-2", 2)]
    assert listed[0].restored_from is None
    assert listed[0].created_by is None
    _, args = pool.calls[0]
    assert args == ("d-1",)


async def test_snapshot_latest_maps_the_row():
    pool = FakePool(row=snapshot_row(seq=7))
    latest = await PostgresSnapshotRepository(pool).latest(DocumentId("d-1"))

    assert latest.seq == 7
    assert latest.content == {"blocks": []}
    query, args = pool.calls[0]
    assert "ORDER BY seq DESC LIMIT 1" in query
    assert args == ("d-1",)


async def test_snapshot_latest_returns_none_without_snapshots():
    pool = FakePool(row=None)
    assert await PostgresSnapshotRepository(pool).latest(DocumentId("d-1")) is None


# --- PostgresMembershipRepository -------------------------------------------


async def test_add_workspace_member_upserts_with_role_value():
    pool = FakePool()
    membership = WorkspaceMembership(
        workspace_id=WorkspaceId("ws-1"),
        user_id=UserId("bob"),
        role=Role.EDITOR,
        granted_at=NOW,
    )
    await PostgresMembershipRepository(pool).add_workspace_member(membership)

    query, args = pool.calls[0]
    assert query.startswith("INSERT INTO workspace_memberships")
    assert "ON CONFLICT (workspace_id, user_id) DO UPDATE" in query
    assert args == ("ws-1", "bob", "editor", NOW)


async def test_workspace_role_maps_the_row():
    pool = FakePool(
        row={
            "workspace_id": "ws-1",
            "user_id": "bob",
            "role": "editor",
            "granted_at": NOW,
        }
    )
    membership = await PostgresMembershipRepository(pool).workspace_role(
        WorkspaceId("ws-1"), UserId("bob")
    )

    assert membership == WorkspaceMembership(
        workspace_id=WorkspaceId("ws-1"),
        user_id=UserId("bob"),
        role=Role.EDITOR,
        granted_at=NOW,
    )
    _, args = pool.calls[0]
    assert args == ("ws-1", "bob")


async def test_workspace_role_returns_none_for_non_members():
    pool = FakePool(row=None)
    repo = PostgresMembershipRepository(pool)
    assert await repo.workspace_role(WorkspaceId("ws-1"), UserId("carol")) is None


async def test_add_document_grant_upserts_with_role_value():
    pool = FakePool()
    grant = DocumentGrant(
        document_id=DocumentId("d-1"),
        user_id=UserId("carol"),
        role=Role.VIEWER,
        granted_at=NOW,
    )
    await PostgresMembershipRepository(pool).add_document_grant(grant)

    query, args = pool.calls[0]
    assert query.startswith("INSERT INTO document_grants")
    assert "ON CONFLICT (document_id, user_id) DO UPDATE" in query
    assert args == ("d-1", "carol", "viewer", NOW)


async def test_document_grant_maps_the_row():
    pool = FakePool(
        row={
            "document_id": "d-1",
            "user_id": "carol",
            "role": "viewer",
            "granted_at": NOW,
        }
    )
    grant = await PostgresMembershipRepository(pool).document_grant(
        DocumentId("d-1"), UserId("carol")
    )

    assert grant == DocumentGrant(
        document_id=DocumentId("d-1"),
        user_id=UserId("carol"),
        role=Role.VIEWER,
        granted_at=NOW,
    )
    _, args = pool.calls[0]
    assert args == ("d-1", "carol")


async def test_document_grant_returns_none_when_absent():
    pool = FakePool(row=None)
    repo = PostgresMembershipRepository(pool)
    assert await repo.document_grant(DocumentId("d-1"), UserId("mallory")) is None


async def test_document_grants_for_user_maps_rows():
    pool = FakePool(
        rows=[
            {"document_id": "d-2", "user_id": "carol", "role": "editor", "granted_at": NOW},
            {"document_id": "d-1", "user_id": "carol", "role": "viewer", "granted_at": NOW},
        ]
    )
    grants = await PostgresMembershipRepository(pool).document_grants_for_user(
        UserId("carol")
    )

    assert [(g.document_id, g.role) for g in grants] == [
        (DocumentId("d-2"), Role.EDITOR),
        (DocumentId("d-1"), Role.VIEWER),
    ]
    _, args = pool.calls[0]
    assert args == ("carol",)
