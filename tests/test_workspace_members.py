"""workspace-members spec: listing, role changes, removal, last-owner rule."""

from __future__ import annotations

import pytest

from cyberarche.application.testing.fakes import InMemoryDirectory
from cyberarche.application.ports.identity import DirectoryUser
from cyberarche.application.use_cases import UseCases
from cyberarche.domain.errors import Conflict, NotAuthorized, NotFound
from cyberarche.domain.memberships import Role
from tests.conftest import caller

BOB = caller("bob", "acme")
CAROL = caller("carol", "acme")


async def workspace_with_bob(use_cases: UseCases, alice, role: Role = Role.EDITOR):
    workspace = await use_cases.workspaces.create(alice, name="WS")
    await use_cases.sharing.invite_to_workspace(
        alice, workspace.id, user_id=BOB.user_id, role=role
    )
    return workspace


# ---- listing ----------------------------------------------------------------

async def test_any_member_lists_members(use_cases: UseCases, alice):
    workspace = await workspace_with_bob(use_cases, alice)

    listed = await use_cases.members.list_members(BOB, workspace.id)

    assert [(str(m.membership.user_id), m.membership.role) for m in listed] == [
        ("alice", Role.OWNER),
        ("bob", Role.EDITOR),
    ]


async def test_non_members_cannot_list(use_cases: UseCases, alice):
    workspace = await workspace_with_bob(use_cases, alice)

    with pytest.raises(NotAuthorized):
        await use_cases.members.list_members(CAROL, workspace.id)


async def test_listing_enriches_from_the_directory(
    use_cases: UseCases, alice, directory: InMemoryDirectory
):
    directory.users_by_org["acme"] = [
        DirectoryUser(id="alice", email="alice@acme.test", avatar_url="http://a/1")
    ]
    workspace = await workspace_with_bob(use_cases, alice)

    listed = await use_cases.members.list_members(alice, workspace.id)

    by_id = {str(m.membership.user_id): m for m in listed}
    assert by_id["alice"].email == "alice@acme.test"
    assert by_id["alice"].avatar_url == "http://a/1"
    assert by_id["bob"].email is None  # not in the directory: bare id, no failure


async def test_callers_own_row_falls_back_to_claims_email(use_cases: UseCases):
    """Even without a directory entry, the caller's own row shows their email."""
    from cyberarche.application.kernel import CallerContext
    from cyberarche.domain.ids import TenantId, UserId

    me = CallerContext(
        user_id=UserId("alice"), tenant_id=TenantId("acme"), email="alice@acme.test"
    )
    workspace = await use_cases.workspaces.create(me, name="WS")

    listed = await use_cases.members.list_members(me, workspace.id)

    assert listed[0].email == "alice@acme.test"


async def test_listing_survives_a_directory_outage(use_cases: UseCases, alice):
    workspace = await workspace_with_bob(use_cases, alice)
    failing = _FailingDirectory()
    use_cases.members._directory = failing  # simulate outage after wiring

    listed = await use_cases.members.list_members(alice, workspace.id)

    assert len(listed) == 2
    assert all(m.email is None for m in listed)


class _FailingDirectory:
    async def list_org_users(self, org_id, *, search=None, page=1, page_size=50):
        from cyberarche.domain.errors import UpstreamUnavailable

        raise UpstreamUnavailable("down")


# ---- role changes -----------------------------------------------------------

async def test_owner_changes_a_members_role(use_cases: UseCases, alice):
    workspace = await workspace_with_bob(use_cases, alice)

    updated = await use_cases.members.set_member_role(
        alice, workspace.id, user_id=BOB.user_id, role=Role.COMMENTER
    )

    assert updated.role == Role.COMMENTER
    listed = await use_cases.members.list_members(alice, workspace.id)
    assert {str(m.membership.user_id): m.membership.role for m in listed}["bob"] == (
        Role.COMMENTER
    )


async def test_non_owner_cannot_change_roles(use_cases: UseCases, alice):
    workspace = await workspace_with_bob(use_cases, alice)

    with pytest.raises(NotAuthorized):
        await use_cases.members.set_member_role(
            BOB, workspace.id, user_id=alice.user_id, role=Role.VIEWER
        )


async def test_changing_an_unknown_member_is_not_found(use_cases: UseCases, alice):
    workspace = await use_cases.workspaces.create(alice, name="WS")

    with pytest.raises(NotFound):
        await use_cases.members.set_member_role(
            alice, workspace.id, user_id=CAROL.user_id, role=Role.VIEWER
        )


# ---- removal ----------------------------------------------------------------

async def test_owner_removes_a_member(use_cases: UseCases, alice, memberships):
    workspace = await workspace_with_bob(use_cases, alice)

    await use_cases.members.remove_member(alice, workspace.id, BOB.user_id)

    assert await memberships.workspace_role(workspace.id, BOB.user_id) is None


async def test_non_owner_cannot_remove(use_cases: UseCases, alice):
    workspace = await workspace_with_bob(use_cases, alice)

    with pytest.raises(NotAuthorized):
        await use_cases.members.remove_member(BOB, workspace.id, alice.user_id)


# ---- last-owner protection ---------------------------------------------------

async def test_the_last_owner_cannot_be_demoted(use_cases: UseCases, alice):
    workspace = await workspace_with_bob(use_cases, alice)

    with pytest.raises(Conflict):
        await use_cases.members.set_member_role(
            alice, workspace.id, user_id=alice.user_id, role=Role.EDITOR
        )


async def test_the_last_owner_cannot_be_removed(use_cases: UseCases, alice):
    workspace = await workspace_with_bob(use_cases, alice)

    with pytest.raises(Conflict):
        await use_cases.members.remove_member(alice, workspace.id, alice.user_id)


async def test_one_of_several_owners_can_be_demoted(use_cases: UseCases, alice):
    workspace = await workspace_with_bob(use_cases, alice, role=Role.OWNER)

    updated = await use_cases.members.set_member_role(
        alice, workspace.id, user_id=alice.user_id, role=Role.EDITOR
    )

    assert updated.role == Role.EDITOR


async def test_the_invite_upsert_cannot_demote_the_last_owner(
    use_cases: UseCases, alice
):
    workspace = await workspace_with_bob(use_cases, alice)

    with pytest.raises(Conflict):
        await use_cases.sharing.invite_to_workspace(
            alice, workspace.id, user_id=alice.user_id, role=Role.VIEWER
        )


# ---- HTTP surface -----------------------------------------------------------

def auth(token: str = "alice-token") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_members_endpoints_roundtrip(api):
    workspace = api.post(
        "/api/v1/workspaces", json={"name": "Eng"}, headers=auth()
    ).json()
    api.post(
        f"/api/v1/workspaces/{workspace['id']}/invites",
        json={"user_id": "bob", "role": "editor"},
        headers=auth(),
    )

    members = api.get(
        f"/api/v1/workspaces/{workspace['id']}/members", headers=auth()
    ).json()
    assert [(m["user_id"], m["role"]) for m in members] == [
        ("alice", "owner"),
        ("bob", "editor"),
    ]

    patched = api.patch(
        f"/api/v1/workspaces/{workspace['id']}/members/bob",
        json={"role": "viewer"},
        headers=auth(),
    )
    assert patched.status_code == 200
    assert patched.json()["role"] == "viewer"

    removed = api.delete(
        f"/api/v1/workspaces/{workspace['id']}/members/bob", headers=auth()
    )
    assert removed.status_code == 204

    demote_last_owner = api.patch(
        f"/api/v1/workspaces/{workspace['id']}/members/alice",
        json={"role": "editor"},
        headers=auth(),
    )
    assert demote_last_owner.status_code == 409


def test_members_listing_requires_membership(api):
    workspace = api.post(
        "/api/v1/workspaces", json={"name": "Eng"}, headers=auth()
    ).json()

    denied = api.get(
        f"/api/v1/workspaces/{workspace['id']}/members",
        headers=auth("mallory-token"),
    )
    assert denied.status_code == 403


def test_org_users_endpoint(api):
    response = api.get("/api/v1/org/users", headers=auth())

    assert response.status_code == 200
    body = response.json()
    assert body["users"] == [] and body["total"] == 0
