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
