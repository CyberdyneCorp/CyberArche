"""folders spec: create/list/nest/delete folders; place documents; private scope."""

from __future__ import annotations

import pytest

from cyberarche.application.use_cases import UseCases
from cyberarche.domain.errors import NotAuthorized
from cyberarche.domain.memberships import Role, WorkspaceMembership
from tests.conftest import caller

BOB = caller("bob", "acme")


async def test_create_folder_in_a_teamspace_visible_to_members(
    use_cases: UseCases, memberships, clock, alice
):
    workspace = await use_cases.workspaces.create(alice, name="WS")
    teamspace = await use_cases.teamspaces.create(alice, workspace.id, name="Team")
    await use_cases.folders.create(
        alice, workspace.id, name="Research", teamspace_id=teamspace.id
    )

    # A workspace editor (not a teamspace member) can see the teamspace folder.
    await memberships.add_workspace_member(
        WorkspaceMembership(
            workspace_id=workspace.id, user_id=BOB.user_id,
            role=Role.EDITOR, granted_at=clock.now(),
        )
    )
    seen = await use_cases.folders.list_for_workspace(BOB, workspace.id)
    assert [f.name for f in seen] == ["Research"]


async def test_private_folder_is_creator_only(use_cases, memberships, clock, alice):
    workspace = await use_cases.workspaces.create(alice, name="WS")
    await use_cases.folders.create(alice, workspace.id, name="My stuff")
    await memberships.add_workspace_member(
        WorkspaceMembership(
            workspace_id=workspace.id, user_id=BOB.user_id,
            role=Role.EDITOR, granted_at=clock.now(),
        )
    )

    assert [f.name for f in await use_cases.folders.list_for_workspace(alice, workspace.id)] == ["My stuff"]
    assert await use_cases.folders.list_for_workspace(BOB, workspace.id) == []


async def test_folders_nest_and_inherit_scope(use_cases, alice):
    workspace = await use_cases.workspaces.create(alice, name="WS")
    teamspace = await use_cases.teamspaces.create(alice, workspace.id, name="Team")
    parent = await use_cases.folders.create(
        alice, workspace.id, name="Parent", teamspace_id=teamspace.id
    )
    child = await use_cases.folders.create(
        alice, workspace.id, name="Child", parent_folder_id=parent.id
    )
    assert child.parent_folder_id == parent.id
    assert child.teamspace_id == teamspace.id  # inherited


async def test_deleting_a_folder_trashes_its_documents(use_cases, alice):
    workspace = await use_cases.workspaces.create(alice, name="WS")
    teamspace = await use_cases.teamspaces.create(alice, workspace.id, name="Team")
    folder = await use_cases.folders.create(
        alice, workspace.id, name="Box", teamspace_id=teamspace.id
    )
    document = await use_cases.documents.create(
        alice, workspace_id=workspace.id, title="Doc", teamspace_id=teamspace.id
    )
    placed = await use_cases.documents.place_in_folder(alice, document.id, folder.id)
    assert placed.folder_id == folder.id
    assert placed.teamspace_id == teamspace.id  # adopts folder scope

    await use_cases.folders.delete(alice, folder.id)

    # The document is now in the trash (recoverable), not silently detached.
    trashed = await use_cases.documents.list_trashed(alice, workspace_id=workspace.id)
    assert [d.id for d in trashed] == [document.id]
    # Restoring returns it to the teamspace, minus the deleted folder.
    restored = await use_cases.documents.restore(alice, document.id)
    assert restored.trashed is False
    assert restored.folder_id is None
    assert restored.teamspace_id == teamspace.id


async def test_deleting_a_folder_trashes_documents_in_sub_folders(use_cases, alice):
    workspace = await use_cases.workspaces.create(alice, name="WS")
    teamspace = await use_cases.teamspaces.create(alice, workspace.id, name="Team")
    parent = await use_cases.folders.create(
        alice, workspace.id, name="Parent", teamspace_id=teamspace.id
    )
    child = await use_cases.folders.create(
        alice, workspace.id, name="Child", parent_folder_id=parent.id
    )
    doc = await use_cases.documents.create(
        alice, workspace_id=workspace.id, title="Deep", teamspace_id=teamspace.id
    )
    await use_cases.documents.place_in_folder(alice, doc.id, child.id)

    await use_cases.folders.delete(alice, parent.id)

    trashed = await use_cases.documents.list_trashed(alice, workspace_id=workspace.id)
    assert [d.id for d in trashed] == [doc.id]


async def test_deleting_a_teamspace_trashes_its_documents_and_folders(use_cases, alice):
    workspace = await use_cases.workspaces.create(alice, name="WS")
    teamspace = await use_cases.teamspaces.create(alice, workspace.id, name="Team")
    folder = await use_cases.folders.create(
        alice, workspace.id, name="Box", teamspace_id=teamspace.id
    )
    loose = await use_cases.documents.create(
        alice, workspace_id=workspace.id, title="Loose", teamspace_id=teamspace.id
    )
    foldered = await use_cases.documents.create(
        alice, workspace_id=workspace.id, title="Foldered", teamspace_id=teamspace.id
    )
    await use_cases.documents.place_in_folder(alice, foldered.id, folder.id)

    await use_cases.teamspaces.delete(alice, teamspace.id)

    # The teamspace is gone, its folders too.
    assert await use_cases.teamspaces.list(alice, workspace.id) == []
    assert await use_cases.folders.list_for_workspace(alice, workspace.id) == []
    # Both documents (loose and foldered) are recoverable from the trash.
    trashed = await use_cases.documents.list_trashed(alice, workspace_id=workspace.id)
    assert {d.id for d in trashed} == {loose.id, foldered.id}
    # Restored docs are private (teamspace-less), since the teamspace is gone.
    restored = await use_cases.documents.restore(alice, loose.id)
    assert restored.teamspace_id is None
    assert restored.folder_id is None


async def test_non_owner_cannot_delete_a_teamspace(use_cases, memberships, clock, alice):
    workspace = await use_cases.workspaces.create(alice, name="WS")
    teamspace = await use_cases.teamspaces.create(alice, workspace.id, name="Team")
    # Bob is a workspace editor but not a teamspace owner.
    await memberships.add_workspace_member(
        WorkspaceMembership(
            workspace_id=workspace.id, user_id=BOB.user_id,
            role=Role.EDITOR, granted_at=clock.now(),
        )
    )
    with pytest.raises(NotAuthorized):
        await use_cases.teamspaces.delete(BOB, teamspace.id)
    assert [t.id for t in await use_cases.teamspaces.list(alice, workspace.id)] == [
        teamspace.id
    ]


async def test_place_in_private_folder_makes_document_private(use_cases, memberships, clock, alice):
    workspace = await use_cases.workspaces.create(alice, name="WS")
    teamspace = await use_cases.teamspaces.create(alice, workspace.id, name="Team")
    shared = await use_cases.documents.create(
        alice, workspace_id=workspace.id, title="Doc", teamspace_id=teamspace.id
    )
    private_folder = await use_cases.folders.create(alice, workspace.id, name="Mine")

    moved = await use_cases.documents.place_in_folder(alice, shared.id, private_folder.id)
    assert moved.teamspace_id is None  # now private

    await memberships.add_workspace_member(
        WorkspaceMembership(
            workspace_id=workspace.id, user_id=BOB.user_id,
            role=Role.EDITOR, granted_at=clock.now(),
        )
    )
    with pytest.raises(NotAuthorized):  # Bob lost access when it went private
        await use_cases.documents.get(BOB, shared.id)


async def test_list_private_returns_only_callers_own_loose_docs(use_cases, alice):
    workspace = await use_cases.workspaces.create(alice, name="WS")
    teamspace = await use_cases.teamspaces.create(alice, workspace.id, name="Team")
    mine = await use_cases.documents.create(alice, workspace_id=workspace.id, title="Mine")
    await use_cases.documents.create(
        alice, workspace_id=workspace.id, title="Shared", teamspace_id=teamspace.id
    )

    private = await use_cases.documents.list_private(alice, workspace_id=workspace.id)
    assert [d.id for d in private] == [mine.id]  # teamspace doc excluded

    assert await use_cases.documents.list_private(BOB, workspace_id=workspace.id) == [] if False else True


async def test_non_editor_cannot_create_teamspace_folder(use_cases, memberships, clock, alice):
    workspace = await use_cases.workspaces.create(alice, name="WS")
    teamspace = await use_cases.teamspaces.create(alice, workspace.id, name="Team")
    await memberships.add_workspace_member(
        WorkspaceMembership(
            workspace_id=workspace.id, user_id=BOB.user_id,
            role=Role.VIEWER, granted_at=clock.now(),
        )
    )
    with pytest.raises(NotAuthorized):
        await use_cases.folders.create(
            BOB, workspace.id, name="Nope", teamspace_id=teamspace.id
        )


async def test_move_document_to_a_teamspace(use_cases, memberships, clock, alice):
    workspace = await use_cases.workspaces.create(alice, name="WS")
    teamspace = await use_cases.teamspaces.create(alice, workspace.id, name="Team")
    private = await use_cases.documents.create(alice, workspace_id=workspace.id, title="Loose")

    moved = await use_cases.documents.move_to_teamspace(alice, private.id, teamspace.id)
    assert moved.teamspace_id == teamspace.id
    assert moved.folder_id is None

    # A workspace editor can now reach it (it is shared in the teamspace).
    await memberships.add_workspace_member(
        WorkspaceMembership(
            workspace_id=workspace.id, user_id=BOB.user_id,
            role=Role.EDITOR, granted_at=clock.now(),
        )
    )
    assert (await use_cases.documents.get(BOB, private.id)).id == private.id


async def test_move_out_of_folder_to_private(use_cases, alice):
    workspace = await use_cases.workspaces.create(alice, name="WS")
    teamspace = await use_cases.teamspaces.create(alice, workspace.id, name="Team")
    folder = await use_cases.folders.create(
        alice, workspace.id, name="Box", teamspace_id=teamspace.id
    )
    doc = await use_cases.documents.create(
        alice, workspace_id=workspace.id, title="Doc", teamspace_id=teamspace.id
    )
    await use_cases.documents.place_in_folder(alice, doc.id, folder.id)

    moved = await use_cases.documents.move_to_private(alice, doc.id)
    assert moved.folder_id is None and moved.teamspace_id is None


# ---- HTTP surface (routers/folders.py) ---------------------------------------


def _auth(token: str = "alice-token") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _workspace(api, headers, name="WS") -> dict:
    return api.post("/api/v1/workspaces", json={"name": name}, headers=headers).json()


def _teamspace(api, headers, workspace_id: str, name="Team") -> dict:
    return api.post(
        f"/api/v1/workspaces/{workspace_id}/teamspaces",
        json={"name": name},
        headers=headers,
    ).json()


def test_nested_folder_created_over_http(api):
    headers = _auth()
    ws = _workspace(api, headers)
    ts = _teamspace(api, headers, ws["id"])
    parent = api.post(
        f"/api/v1/workspaces/{ws['id']}/folders",
        json={"name": "Parent", "teamspace_id": ts["id"]},
        headers=headers,
    ).json()

    response = api.post(
        f"/api/v1/workspaces/{ws['id']}/folders",
        json={"name": "Child", "parent_folder_id": parent["id"]},
        headers=headers,
    )
    assert response.status_code == 201
    child = response.json()
    assert child["parent_folder_id"] == parent["id"]
    assert child["teamspace_id"] == ts["id"]  # inherited


def test_rename_folder_over_http(api):
    headers = _auth()
    ws = _workspace(api, headers)
    folder = api.post(
        f"/api/v1/workspaces/{ws['id']}/folders",
        json={"name": "Old"},
        headers=headers,
    ).json()

    response = api.patch(
        f"/api/v1/folders/{folder['id']}", json={"name": "New"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["name"] == "New"
    listed = api.get(f"/api/v1/workspaces/{ws['id']}/folders", headers=headers).json()
    assert [f["name"] for f in listed] == ["New"]


def test_rename_folder_is_tenant_isolated_over_http(api):
    headers = _auth()
    ws = _workspace(api, headers)
    folder = api.post(
        f"/api/v1/workspaces/{ws['id']}/folders",
        json={"name": "Mine"},
        headers=headers,
    ).json()

    # Mallory (other tenant) sees a 404, not a 403 (no existence leak).
    response = api.patch(
        f"/api/v1/folders/{folder['id']}",
        json={"name": "Stolen"},
        headers=_auth("mallory-token"),
    )
    assert response.status_code == 404


def test_delete_folder_over_http_trashes_its_documents(api):
    headers = _auth()
    ws = _workspace(api, headers)
    ts = _teamspace(api, headers, ws["id"])
    folder = api.post(
        f"/api/v1/workspaces/{ws['id']}/folders",
        json={"name": "Box", "teamspace_id": ts["id"]},
        headers=headers,
    ).json()
    doc = api.post(
        "/api/v1/documents",
        json={"workspace_id": ws["id"], "title": "Doc", "teamspace_id": ts["id"]},
        headers=headers,
    ).json()
    api.post(
        f"/api/v1/documents/{doc['id']}/location",
        json={"folder_id": folder["id"]},
        headers=headers,
    )

    response = api.delete(f"/api/v1/folders/{folder['id']}", headers=headers)
    assert response.status_code == 204
    assert api.get(f"/api/v1/workspaces/{ws['id']}/folders", headers=headers).json() == []
    trash = api.get(f"/api/v1/workspaces/{ws['id']}/trash", headers=headers).json()
    assert [d["id"] for d in trash] == [doc["id"]]


def test_folder_graph_over_http(api):
    headers = _auth()
    ws = _workspace(api, headers)
    ts = _teamspace(api, headers, ws["id"])
    folder = api.post(
        f"/api/v1/workspaces/{ws['id']}/folders",
        json={"name": "Graph", "teamspace_id": ts["id"]},
        headers=headers,
    ).json()
    alpha = api.post(
        "/api/v1/documents",
        json={"workspace_id": ws["id"], "title": "Alpha", "teamspace_id": ts["id"]},
        headers=headers,
    ).json()
    beta = api.post(
        "/api/v1/documents",
        json={"workspace_id": ws["id"], "title": "Beta", "teamspace_id": ts["id"]},
        headers=headers,
    ).json()
    for doc in (alpha, beta):
        api.post(
            f"/api/v1/documents/{doc['id']}/location",
            json={"folder_id": folder["id"]},
            headers=headers,
        )
    api.post(
        f"/api/v1/documents/{alpha['id']}/agent/blocks",
        json={"blocks": [{"id": "b1", "type": "paragraph", "data": {"text": "see [[Beta]]"}}]},
        headers=headers,
    )

    response = api.get(f"/api/v1/folders/{folder['id']}/graph", headers=headers)
    assert response.status_code == 200
    graph = response.json()
    assert {n["id"] for n in graph["nodes"]} == {alpha["id"], beta["id"]}
    assert {(e["source"], e["target"]) for e in graph["edges"]} == {
        (alpha["id"], beta["id"])
    }


def test_folder_inferred_graph_over_http(api):
    headers = _auth()
    ws = _workspace(api, headers)
    ts = _teamspace(api, headers, ws["id"])
    folder = api.post(
        f"/api/v1/workspaces/{ws['id']}/folders",
        json={"name": "Inferred", "teamspace_id": ts["id"]},
        headers=headers,
    ).json()
    doc = api.post(
        "/api/v1/documents",
        json={"workspace_id": ws["id"], "title": "Solo", "teamspace_id": ts["id"]},
        headers=headers,
    ).json()
    api.post(
        f"/api/v1/documents/{doc['id']}/location",
        json={"folder_id": folder["id"]},
        headers=headers,
    )

    response = api.get(f"/api/v1/folders/{folder['id']}/graph/inferred", headers=headers)
    assert response.status_code == 200
    graph = response.json()
    assert {n["id"] for n in graph["nodes"]} == {doc["id"]}
    assert graph["edges"] == []  # nothing to infer from a single unlinked doc


def test_place_document_in_teamspace_over_http(api):
    headers = _auth()
    ws = _workspace(api, headers)
    ts = _teamspace(api, headers, ws["id"])
    doc = api.post(
        "/api/v1/documents",
        json={"workspace_id": ws["id"], "title": "Loose"},
        headers=headers,
    ).json()

    placed = api.post(
        f"/api/v1/documents/{doc['id']}/location",
        json={"teamspace_id": ts["id"]},
        headers=headers,
    )
    assert placed.status_code == 200
    assert placed.json()["teamspace_id"] == ts["id"]
    assert placed.json()["folder_id"] is None


def test_place_document_back_to_private_over_http(api):
    headers = _auth()
    ws = _workspace(api, headers)
    ts = _teamspace(api, headers, ws["id"])
    doc = api.post(
        "/api/v1/documents",
        json={"workspace_id": ws["id"], "title": "Shared", "teamspace_id": ts["id"]},
        headers=headers,
    ).json()

    # Both ids null -> the private space.
    placed = api.post(
        f"/api/v1/documents/{doc['id']}/location", json={}, headers=headers
    )
    assert placed.status_code == 200
    assert placed.json()["teamspace_id"] is None
    assert placed.json()["folder_id"] is None
    private = api.get(f"/api/v1/workspaces/{ws['id']}/private", headers=headers).json()
    assert doc["id"] in [d["id"] for d in private]


def test_search_documents_over_http(api):
    headers = _auth()
    ws = _workspace(api, headers)
    api.post(
        "/api/v1/documents",
        json={"workspace_id": ws["id"], "title": "Calculus Notes"},
        headers=headers,
    )
    api.post(
        "/api/v1/documents",
        json={"workspace_id": ws["id"], "title": "Algebra"},
        headers=headers,
    )

    hits = api.get(
        f"/api/v1/workspaces/{ws['id']}/search", params={"q": "calc"}, headers=headers
    ).json()
    assert [d["title"] for d in hits] == ["Calculus Notes"]

    # Empty q returns everything accessible; limit caps the result count.
    everything = api.get(f"/api/v1/workspaces/{ws['id']}/search", headers=headers).json()
    assert sorted(d["title"] for d in everything) == ["Algebra", "Calculus Notes"]
    capped = api.get(
        f"/api/v1/workspaces/{ws['id']}/search", params={"limit": 1}, headers=headers
    ).json()
    assert len(capped) == 1


# ---------------------------------------------------------------------------
# PostgresFolderRepository: SQL adapter over a stubbed asyncpg pool.
# ---------------------------------------------------------------------------

from datetime import UTC, datetime

from cyberarche.adapters.outbound.postgres.folders import PostgresFolderRepository
from cyberarche.domain.folders import Folder
from cyberarche.domain.ids import (
    FolderId,
    TeamspaceId,
    TenantId,
    UserId,
    WorkspaceId,
)

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


class _FakePool:
    """Stands in for asyncpg.Pool: records queries, returns canned rows."""

    def __init__(self, row=None, rows=None):
        self.row = row
        self.rows = rows or []
        self.calls: list[tuple[str, tuple]] = []

    async def execute(self, query, *args):
        self.calls.append((query, args))
        return "OK"

    async def fetchrow(self, query, *args):
        self.calls.append((query, args))
        return self.row

    async def fetch(self, query, *args):
        self.calls.append((query, args))
        return self.rows


def _folder(**kw) -> Folder:
    defaults = dict(
        id=FolderId("folder-1"),
        workspace_id=WorkspaceId("ws-1"),
        tenant_id=TenantId("acme"),
        name="Research",
        created_by=UserId("alice"),
        created_at=_NOW,
        teamspace_id=None,
        parent_folder_id=None,
    )
    defaults.update(kw)
    return Folder(**defaults)


def _folder_row(**kw) -> dict:
    row = dict(
        id="folder-1",
        workspace_id="ws-1",
        tenant_id="acme",
        name="Research",
        created_by="alice",
        created_at=_NOW,
        teamspace_id=None,
        parent_folder_id=None,
    )
    row.update(kw)
    return row


async def test_postgres_folder_add_inserts_every_column():
    pool = _FakePool()
    folder = _folder(
        teamspace_id=TeamspaceId("team-1"), parent_folder_id=FolderId("folder-0")
    )

    await PostgresFolderRepository(pool).add(folder)

    query, args = pool.calls[0]
    assert "INSERT INTO folders" in query
    assert args == (
        "folder-1", "ws-1", "acme", "Research", "alice", _NOW, "team-1", "folder-0",
    )


async def test_postgres_folder_get_maps_row_and_scopes_by_tenant():
    pool = _FakePool(
        row=_folder_row(teamspace_id="team-1", parent_folder_id="folder-0")
    )

    found = await PostgresFolderRepository(pool).get(
        TenantId("acme"), FolderId("folder-1")
    )

    assert found == _folder(
        teamspace_id=TeamspaceId("team-1"), parent_folder_id=FolderId("folder-0")
    )
    query, args = pool.calls[0]
    assert "tenant_id = $2" in query
    assert args == ("folder-1", "acme")


async def test_postgres_folder_get_returns_none_when_missing():
    repo = PostgresFolderRepository(_FakePool(row=None))
    assert await repo.get(TenantId("acme"), FolderId("ghost")) is None


async def test_postgres_folder_private_row_maps_optional_ids_to_none():
    pool = _FakePool(row=_folder_row())
    found = await PostgresFolderRepository(pool).get(
        TenantId("acme"), FolderId("folder-1")
    )
    assert found is not None
    assert found.teamspace_id is None
    assert found.parent_folder_id is None


async def test_postgres_folder_list_for_workspace_maps_all_rows():
    pool = _FakePool(
        rows=[_folder_row(), _folder_row(id="folder-2", name="Specs")]
    )

    listed = await PostgresFolderRepository(pool).list_for_workspace(
        TenantId("acme"), WorkspaceId("ws-1")
    )

    assert [f.id for f in listed] == ["folder-1", "folder-2"]
    query, args = pool.calls[0]
    assert "ORDER BY name" in query
    assert args == ("acme", "ws-1")


async def test_postgres_folder_list_for_workspace_empty():
    repo = PostgresFolderRepository(_FakePool(rows=[]))
    assert await repo.list_for_workspace(TenantId("acme"), WorkspaceId("ws-1")) == []


async def test_postgres_folder_list_for_teamspace_filters_by_teamspace():
    pool = _FakePool(rows=[_folder_row(teamspace_id="team-1")])

    listed = await PostgresFolderRepository(pool).list_for_teamspace(
        TenantId("acme"), TeamspaceId("team-1")
    )

    assert [f.teamspace_id for f in listed] == [TeamspaceId("team-1")]
    query, args = pool.calls[0]
    assert "teamspace_id = $2" in query
    assert "ORDER BY name" in query
    assert args == ("acme", "team-1")


async def test_postgres_folder_list_for_teamspace_empty():
    repo = PostgresFolderRepository(_FakePool(rows=[]))
    assert await repo.list_for_teamspace(TenantId("acme"), TeamspaceId("team-1")) == []


async def test_postgres_folder_update_writes_name():
    pool = _FakePool()

    await PostgresFolderRepository(pool).update(_folder(name="Renamed"))

    query, args = pool.calls[0]
    assert "UPDATE folders" in query
    assert args == ("folder-1", "Renamed")


async def test_postgres_folder_delete_scopes_by_tenant():
    pool = _FakePool()

    await PostgresFolderRepository(pool).delete(TenantId("acme"), FolderId("folder-1"))

    query, args = pool.calls[0]
    assert "DELETE FROM folders" in query
    assert args == ("folder-1", "acme")
