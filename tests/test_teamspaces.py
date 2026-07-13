"""teamspaces + favorites specs, and the strongest-role rule (design D-1)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from cyberarche.adapters.outbound.postgres.teamspaces import (
    PostgresFavoriteRepository,
    PostgresTeamspaceRepository,
)
from cyberarche.application.use_cases import UseCases
from cyberarche.domain.errors import NotAuthorized, ValidationFailed
from cyberarche.domain.ids import (
    DocumentId,
    TeamspaceId,
    TenantId,
    UserId,
    WorkspaceId,
)
from cyberarche.domain.memberships import Role
from cyberarche.domain.teamspaces import Teamspace, TeamspaceMembership
from tests.conftest import caller

BOB = caller("bob", "acme")  # no workspace role unless granted
CAROL = caller("carol", "acme")


async def test_create_makes_the_creator_an_owner(use_cases: UseCases, alice):
    workspace = await use_cases.workspaces.create(alice, name="WS")

    teamspace = await use_cases.teamspaces.create(alice, workspace.id, name="Tessera")

    assert teamspace.workspace_id == workspace.id
    members = await use_cases.teamspaces.members(alice, teamspace.id)
    assert [(m.user_id, m.role) for m in members] == [(alice.user_id, Role.OWNER)]


async def test_documents_live_under_their_teamspace(use_cases: UseCases, alice):
    workspace = await use_cases.workspaces.create(alice, name="WS")
    teamspace = await use_cases.teamspaces.create(alice, workspace.id, name="Tessera")

    inside = await use_cases.documents.create(
        alice, workspace_id=workspace.id, title="Team doc", teamspace_id=teamspace.id
    )
    await use_cases.documents.create(alice, workspace_id=workspace.id, title="Loose doc")

    listed = await use_cases.teamspaces.documents(alice, teamspace.id)
    assert [d.id for d in listed] == [inside.id]
    assert inside.teamspace_id == teamspace.id


async def test_cross_workspace_teamspace_is_rejected(use_cases: UseCases, alice):
    ws_a = await use_cases.workspaces.create(alice, name="A")
    ws_b = await use_cases.workspaces.create(alice, name="B")
    teamspace = await use_cases.teamspaces.create(alice, ws_b.id, name="B team")

    with pytest.raises(ValidationFailed):
        await use_cases.documents.create(
            alice, workspace_id=ws_a.id, title="x", teamspace_id=teamspace.id
        )


async def test_teamspace_membership_grants_document_access(
    use_cases: UseCases, alice
):
    """The point of teamspaces: a user with NO workspace role can work in one."""
    workspace = await use_cases.workspaces.create(alice, name="WS")
    teamspace = await use_cases.teamspaces.create(alice, workspace.id, name="Tessera")
    document = await use_cases.documents.create(
        alice, workspace_id=workspace.id, title="Team doc", teamspace_id=teamspace.id
    )

    with pytest.raises(NotAuthorized):  # before joining
        await use_cases.agent.apply_blocks(
            BOB, document.id, [{"id": "b", "type": "paragraph", "data": {}}]
        )

    await use_cases.teamspaces.add_member(
        alice, teamspace.id, user_id=BOB.user_id, role=Role.EDITOR
    )

    fetched = await use_cases.documents.get(BOB, document.id)
    assert fetched.id == document.id
    await use_cases.agent.apply_blocks(
        BOB, document.id, [{"id": "b", "type": "paragraph", "data": {"text": "hi"}}]
    )


async def test_effective_role_is_the_strongest_of_workspace_and_teamspace(
    use_cases: UseCases, memberships, clock, alice
):
    from cyberarche.domain.memberships import WorkspaceMembership

    workspace = await use_cases.workspaces.create(alice, name="WS")
    teamspace = await use_cases.teamspaces.create(alice, workspace.id, name="T")
    document = await use_cases.documents.create(
        alice, workspace_id=workspace.id, title="Doc", teamspace_id=teamspace.id
    )
    # Weak workspace role, strong teamspace role -> the teamspace wins.
    await memberships.add_workspace_member(
        WorkspaceMembership(
            workspace_id=workspace.id, user_id=BOB.user_id,
            role=Role.VIEWER, granted_at=clock.now(),
        )
    )
    await use_cases.teamspaces.add_member(
        alice, teamspace.id, user_id=BOB.user_id, role=Role.EDITOR
    )

    await use_cases.agent.apply_blocks(
        BOB, document.id, [{"id": "b", "type": "paragraph", "data": {}}]
    )


async def test_document_grant_still_overrides_a_stronger_teamspace_role(
    use_cases: UseCases, alice
):
    """A deliberate demotion must not be undone by teamspace membership."""
    workspace = await use_cases.workspaces.create(alice, name="WS")
    teamspace = await use_cases.teamspaces.create(alice, workspace.id, name="T")
    document = await use_cases.documents.create(
        alice, workspace_id=workspace.id, title="Doc", teamspace_id=teamspace.id
    )
    await use_cases.teamspaces.add_member(
        alice, teamspace.id, user_id=BOB.user_id, role=Role.EDITOR
    )

    await use_cases.sharing.grant_on_document(
        alice, document.id, user_id=BOB.user_id, role=Role.VIEWER
    )

    with pytest.raises(NotAuthorized):
        await use_cases.agent.apply_blocks(
            BOB, document.id, [{"id": "b", "type": "paragraph", "data": {}}]
        )


async def test_only_teamspace_owners_manage_membership(use_cases: UseCases, alice):
    workspace = await use_cases.workspaces.create(alice, name="WS")
    teamspace = await use_cases.teamspaces.create(alice, workspace.id, name="T")
    await use_cases.teamspaces.add_member(
        alice, teamspace.id, user_id=BOB.user_id, role=Role.EDITOR
    )

    with pytest.raises(NotAuthorized):
        await use_cases.teamspaces.add_member(
            BOB, teamspace.id, user_id=CAROL.user_id, role=Role.VIEWER
        )


async def test_non_member_without_workspace_role_sees_no_teamspaces(
    use_cases: UseCases, alice
):
    workspace = await use_cases.workspaces.create(alice, name="WS")
    teamspace = await use_cases.teamspaces.create(alice, workspace.id, name="T")

    assert await use_cases.teamspaces.list(BOB, workspace.id) == []
    with pytest.raises(NotAuthorized):
        await use_cases.teamspaces.documents(BOB, teamspace.id)

    await use_cases.teamspaces.add_member(
        alice, teamspace.id, user_id=BOB.user_id, role=Role.VIEWER
    )
    assert [t.id for t in await use_cases.teamspaces.list(BOB, workspace.id)] == [
        teamspace.id
    ]


async def test_removing_a_member_revokes_access(use_cases: UseCases, alice):
    workspace = await use_cases.workspaces.create(alice, name="WS")
    teamspace = await use_cases.teamspaces.create(alice, workspace.id, name="T")
    document = await use_cases.documents.create(
        alice, workspace_id=workspace.id, title="Doc", teamspace_id=teamspace.id
    )
    await use_cases.teamspaces.add_member(
        alice, teamspace.id, user_id=BOB.user_id, role=Role.EDITOR
    )
    await use_cases.documents.get(BOB, document.id)

    await use_cases.teamspaces.remove_member(alice, teamspace.id, BOB.user_id)

    with pytest.raises(NotAuthorized):
        await use_cases.documents.get(BOB, document.id)


# ---- favourites -------------------------------------------------------------


async def test_favorites_are_per_user_and_require_view_access(
    use_cases: UseCases, alice
):
    workspace = await use_cases.workspaces.create(alice, name="WS")
    document = await use_cases.documents.create(
        alice, workspace_id=workspace.id, title="Fav"
    )

    await use_cases.favorites.add(alice, document.id)
    assert [d.id for d in await use_cases.favorites.list(alice)] == [document.id]
    assert await use_cases.favorites.list(BOB) == []  # private to alice

    with pytest.raises(NotAuthorized):  # bob cannot even favourite it
        await use_cases.favorites.add(BOB, document.id)

    await use_cases.favorites.remove(alice, document.id)
    assert await use_cases.favorites.list(alice) == []


async def test_trashed_favorites_drop_out_of_the_list(use_cases: UseCases, alice):
    workspace = await use_cases.workspaces.create(alice, name="WS")
    document = await use_cases.documents.create(
        alice, workspace_id=workspace.id, title="Fav"
    )
    await use_cases.favorites.add(alice, document.id)

    await use_cases.documents.trash(alice, document.id)

    assert await use_cases.favorites.list(alice) == []


def test_teamspace_and_favorite_http_flow(api):
    headers = {"Authorization": "Bearer alice-token"}
    workspace = api.post(
        "/api/v1/workspaces", json={"name": "WS"}, headers=headers
    ).json()

    teamspace = api.post(
        f"/api/v1/workspaces/{workspace['id']}/teamspaces",
        json={"name": "Tessera", "icon": "T"},
        headers=headers,
    )
    assert teamspace.status_code == 201
    teamspace = teamspace.json()

    document = api.post(
        "/api/v1/documents",
        json={
            "workspace_id": workspace["id"],
            "title": "Team doc",
            "teamspace_id": teamspace["id"],
        },
        headers=headers,
    ).json()
    assert document["teamspace_id"] == teamspace["id"]

    listed = api.get(
        f"/api/v1/teamspaces/{teamspace['id']}/documents", headers=headers
    ).json()
    assert [d["id"] for d in listed] == [document["id"]]

    assert api.post(
        "/api/v1/favorites", json={"document_id": document["id"]}, headers=headers
    ).status_code == 204
    favorites = api.get("/api/v1/favorites", headers=headers).json()
    assert [d["id"] for d in favorites] == [document["id"]]

    # Another tenant sees neither.
    other = {"Authorization": "Bearer mallory-token"}
    assert api.get("/api/v1/favorites", headers=other).json() == []
    assert api.get(
        f"/api/v1/workspaces/{workspace['id']}/teamspaces", headers=other
    ).json() == []


# --- Postgres adapter (fake pool: records queries, replays canned rows) -----

NOW = datetime(2026, 1, 1, tzinfo=UTC)


class FakePool:
    """Minimal asyncpg.Pool stand-in: records queries, replays canned rows."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple]] = []
        self.rows: list[dict] = []
        self.row: dict | None = None
        self.value: object = None

    def _record(self, query: str, args: tuple) -> None:
        self.calls.append((" ".join(query.split()), args))

    async def execute(self, query: str, *args: object) -> str:
        self._record(query, args)
        return "OK"

    async def fetch(self, query: str, *args: object) -> list[dict]:
        self._record(query, args)
        return self.rows

    async def fetchrow(self, query: str, *args: object) -> dict | None:
        self._record(query, args)
        return self.row

    async def fetchval(self, query: str, *args: object) -> object:
        self._record(query, args)
        return self.value


def _teamspace_row(**overrides: object) -> dict:
    row = {
        "id": "ts-1",
        "workspace_id": "ws-1",
        "tenant_id": "acme",
        "name": "Tessera",
        "icon": "T",
        "created_by": "alice",
        "created_at": NOW,
    }
    row.update(overrides)
    return row


def _teamspace() -> Teamspace:
    return Teamspace(
        id=TeamspaceId("ts-1"),
        workspace_id=WorkspaceId("ws-1"),
        tenant_id=TenantId("acme"),
        name="Tessera",
        icon="T",
        created_by=UserId("alice"),
        created_at=NOW,
    )


async def test_pg_teamspace_add_inserts_all_columns():
    pool = FakePool()
    await PostgresTeamspaceRepository(pool).add(_teamspace())

    query, args = pool.calls[0]
    assert query.startswith("INSERT INTO teamspaces")
    assert args == ("ts-1", "ws-1", "acme", "Tessera", "T", "alice", NOW)


async def test_pg_teamspace_get_maps_row():
    pool = FakePool()
    pool.row = _teamspace_row()
    found = await PostgresTeamspaceRepository(pool).get(
        TenantId("acme"), TeamspaceId("ts-1")
    )

    assert found == _teamspace()
    assert pool.calls[0][1] == ("ts-1", "acme")


async def test_pg_teamspace_get_returns_none_when_missing():
    pool = FakePool()
    found = await PostgresTeamspaceRepository(pool).get(
        TenantId("acme"), TeamspaceId("nope")
    )
    assert found is None


async def test_pg_teamspace_list_for_workspace_maps_rows():
    pool = FakePool()
    pool.rows = [_teamspace_row(), _teamspace_row(id="ts-2", name="Beta")]
    listed = await PostgresTeamspaceRepository(pool).list_for_workspace(
        TenantId("acme"), WorkspaceId("ws-1")
    )

    assert [t.id for t in listed] == ["ts-1", "ts-2"]
    assert listed[1].name == "Beta"
    assert pool.calls[0][1] == ("acme", "ws-1")


async def test_pg_teamspace_add_member_upserts_role_value():
    pool = FakePool()
    membership = TeamspaceMembership(
        teamspace_id=TeamspaceId("ts-1"),
        user_id=UserId("bob"),
        role=Role.EDITOR,
        granted_at=NOW,
    )
    await PostgresTeamspaceRepository(pool).add_member(membership)

    query, args = pool.calls[0]
    assert "ON CONFLICT (teamspace_id, user_id) DO UPDATE" in query
    assert args == ("ts-1", "bob", "editor", NOW)


async def test_pg_teamspace_remove_member_deletes_by_pair():
    pool = FakePool()
    await PostgresTeamspaceRepository(pool).remove_member(
        TeamspaceId("ts-1"), UserId("bob")
    )

    query, args = pool.calls[0]
    assert query.startswith("DELETE FROM teamspace_memberships")
    assert args == ("ts-1", "bob")


async def test_pg_teamspace_member_role_maps_row_or_none():
    pool = FakePool()
    repo = PostgresTeamspaceRepository(pool)
    assert await repo.member_role(TeamspaceId("ts-1"), UserId("bob")) is None

    pool.row = {
        "teamspace_id": "ts-1",
        "user_id": "bob",
        "role": "owner",
        "granted_at": NOW,
    }
    membership = await repo.member_role(TeamspaceId("ts-1"), UserId("bob"))
    assert membership == TeamspaceMembership(
        teamspace_id=TeamspaceId("ts-1"),
        user_id=UserId("bob"),
        role=Role.OWNER,
        granted_at=NOW,
    )


async def test_pg_teamspace_members_maps_rows():
    pool = FakePool()
    pool.rows = [
        {"teamspace_id": "ts-1", "user_id": "alice", "role": "owner", "granted_at": NOW},
        {"teamspace_id": "ts-1", "user_id": "bob", "role": "viewer", "granted_at": NOW},
    ]
    members = await PostgresTeamspaceRepository(pool).members(TeamspaceId("ts-1"))

    assert [(m.user_id, m.role) for m in members] == [
        ("alice", Role.OWNER),
        ("bob", Role.VIEWER),
    ]
    assert pool.calls[0][1] == ("ts-1",)


async def test_pg_teamspaces_for_user_joins_memberships():
    pool = FakePool()
    pool.rows = [_teamspace_row()]
    listed = await PostgresTeamspaceRepository(pool).teamspaces_for_user(
        TenantId("acme"), WorkspaceId("ws-1"), UserId("bob")
    )

    assert listed == [_teamspace()]
    query, args = pool.calls[0]
    assert "JOIN teamspace_memberships m ON m.teamspace_id = t.id" in query
    assert args == ("acme", "ws-1", "bob")


async def test_pg_teamspace_delete_scopes_by_tenant():
    pool = FakePool()
    await PostgresTeamspaceRepository(pool).delete(
        TenantId("acme"), TeamspaceId("ts-1")
    )

    query, args = pool.calls[0]
    assert query.startswith("DELETE FROM teamspaces")
    assert args == ("ts-1", "acme")


async def test_pg_favorites_add_is_idempotent_insert():
    pool = FakePool()
    await PostgresFavoriteRepository(pool).add(UserId("alice"), DocumentId("doc-1"))

    query, args = pool.calls[0]
    assert "ON CONFLICT (user_id, document_id) DO NOTHING" in query
    assert args == ("alice", "doc-1")


async def test_pg_favorites_remove_deletes_by_pair():
    pool = FakePool()
    await PostgresFavoriteRepository(pool).remove(UserId("alice"), DocumentId("doc-1"))

    query, args = pool.calls[0]
    assert query.startswith("DELETE FROM favorites")
    assert args == ("alice", "doc-1")


async def test_pg_favorites_list_for_user_maps_document_ids():
    pool = FakePool()
    pool.rows = [{"document_id": "doc-1"}, {"document_id": "doc-2"}]
    listed = await PostgresFavoriteRepository(pool).list_for_user(UserId("alice"))

    assert listed == [DocumentId("doc-1"), DocumentId("doc-2")]
    assert pool.calls[0][1] == ("alice",)


async def test_pg_favorites_is_favorite_truthiness():
    pool = FakePool()
    repo = PostgresFavoriteRepository(pool)
    assert await repo.is_favorite(UserId("alice"), DocumentId("doc-1")) is False

    pool.value = 1
    assert await repo.is_favorite(UserId("alice"), DocumentId("doc-1")) is True
