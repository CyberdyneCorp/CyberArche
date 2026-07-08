"""teamspaces + favorites specs, and the strongest-role rule (design D-1)."""

from __future__ import annotations

import pytest

from cyberarche.application.use_cases import UseCases
from cyberarche.domain.errors import NotAuthorized, ValidationFailed
from cyberarche.domain.memberships import Role
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
