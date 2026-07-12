"""document-model spec: document tree, ordering, tenant isolation, trash."""

from __future__ import annotations

import pytest

from cyberarche.application.use_cases import UseCases
from cyberarche.domain.errors import NotFound, ValidationFailed


async def make_workspace(use_cases: UseCases, caller, name="Docs"):
    return await use_cases.workspaces.create(caller, name=name)


async def test_nested_document_inherits_workspace_and_ordering(
    use_cases: UseCases, alice
):
    workspace = await make_workspace(use_cases, alice)
    parent = await use_cases.documents.create(
        alice, workspace_id=workspace.id, title="Parent"
    )
    child_a = await use_cases.documents.create(
        alice, workspace_id=workspace.id, title="A", parent_id=parent.id
    )
    child_b = await use_cases.documents.create(
        alice, workspace_id=workspace.id, title="B", parent_id=parent.id
    )

    assert child_a.workspace_id == workspace.id
    children = await use_cases.documents.children(
        alice, workspace_id=workspace.id, parent_id=parent.id
    )
    assert [c.id for c in children] == [child_a.id, child_b.id]


async def test_reorder_children_persists_new_order(use_cases: UseCases, alice):
    workspace = await make_workspace(use_cases, alice)
    docs = [
        await use_cases.documents.create(alice, workspace_id=workspace.id, title=t)
        for t in ("one", "two", "three")
    ]

    await use_cases.documents.move(alice, docs[2].id, parent_id=None, position=0)

    children = await use_cases.documents.children(alice, workspace_id=workspace.id)
    assert [c.title for c in children] == ["three", "one", "two"]
    assert [c.position for c in children] == [0, 1, 2]


async def test_documents_are_tenant_isolated(use_cases: UseCases, alice, bob_other_tenant):
    workspace = await make_workspace(use_cases, alice)
    document = await use_cases.documents.create(
        alice, workspace_id=workspace.id, title="Secret"
    )

    with pytest.raises(NotFound):
        await use_cases.documents.get(bob_other_tenant, document.id)


async def test_trash_then_restore_returns_to_previous_parent(use_cases: UseCases, alice):
    workspace = await make_workspace(use_cases, alice)
    parent = await use_cases.documents.create(
        alice, workspace_id=workspace.id, title="Parent"
    )
    child = await use_cases.documents.create(
        alice, workspace_id=workspace.id, title="Child", parent_id=parent.id
    )

    await use_cases.documents.trash(alice, child.id)
    with pytest.raises(NotFound):  # hidden from normal reads
        await use_cases.documents.get(alice, child.id)
    trashed = await use_cases.documents.list_trashed(alice, workspace_id=workspace.id)
    assert [d.id for d in trashed] == [child.id]

    restored = await use_cases.documents.restore(alice, child.id)
    assert restored.trashed is False
    assert restored.parent_id == parent.id


async def test_cannot_move_document_under_its_own_descendant(use_cases: UseCases, alice):
    workspace = await make_workspace(use_cases, alice)
    root = await use_cases.documents.create(alice, workspace_id=workspace.id, title="root")
    child = await use_cases.documents.create(
        alice, workspace_id=workspace.id, title="child", parent_id=root.id
    )

    with pytest.raises(ValidationFailed):
        await use_cases.documents.move(alice, root.id, parent_id=child.id, position=0)


async def test_unknown_block_type_is_rejected():
    from cyberarche.domain.blocks import validate_block_type

    with pytest.raises(ValidationFailed):
        validate_block_type("hologram")
    assert validate_block_type("latex") == "latex"
    # Native Excalidraw canvas block is whitelisted.
    assert validate_block_type("excalidraw") == "excalidraw"
    # Database block (typed rows + views) is whitelisted.
    assert validate_block_type("database") == "database"


# ---- purge (permanent delete from trash) -----------------------------------

from tests.conftest import caller  # noqa: E402

BOB = caller("bob", "acme")


async def test_purge_removes_a_trashed_document_permanently(use_cases: UseCases, alice):
    workspace = await make_workspace(use_cases, alice)
    document = await use_cases.documents.create(
        alice, workspace_id=workspace.id, title="Doomed"
    )
    await use_cases.documents.trash(alice, document.id)

    purged = await use_cases.documents.purge(alice, document.id)
    assert purged == [document.id]

    # Gone from the trash, and not restorable.
    trashed = await use_cases.documents.list_trashed(alice, workspace_id=workspace.id)
    assert document.id not in [d.id for d in trashed]
    with pytest.raises(NotFound):
        await use_cases.documents.restore(alice, document.id)


async def test_purge_cascades_to_the_subtree_and_owned_data(use_cases: UseCases, alice):
    workspace = await make_workspace(use_cases, alice)
    parent = await use_cases.documents.create(
        alice, workspace_id=workspace.id, title="Parent"
    )
    child = await use_cases.documents.create(
        alice, workspace_id=workspace.id, title="Child", parent_id=parent.id
    )
    # Owned data: a snapshot on the parent, a comment on the child.
    await use_cases.snapshots.record(
        alice, parent.id, content={"blocks": []}, state_vector=b"sv"
    )
    await use_cases.agent.apply_blocks(
        alice, child.id, [{"id": "b1", "type": "paragraph", "data": {"text": "x"}}]
    )
    await use_cases.sharing.add_comment(alice, child.id, block_id="b1", body="hi")

    await use_cases.documents.trash(alice, parent.id)
    purged = await use_cases.documents.purge(alice, parent.id)

    assert set(purged) == {parent.id, child.id}  # subtree came along
    with pytest.raises(NotFound):
        await use_cases.documents.get(alice, child.id)
    # Owned data is unreachable once the document is gone. (Postgres cascades
    # the rows physically; the contract test asserts that against real SQL.)
    with pytest.raises(NotFound):
        await use_cases.snapshots.list(alice, parent.id)
    with pytest.raises(NotFound):
        await use_cases.sharing.list_comments(alice, child.id)


async def test_a_live_document_cannot_be_purged(use_cases: UseCases, alice):
    workspace = await make_workspace(use_cases, alice)
    document = await use_cases.documents.create(
        alice, workspace_id=workspace.id, title="Alive"
    )

    with pytest.raises(ValidationFailed):
        await use_cases.documents.purge(alice, document.id)

    # Untouched: still readable.
    assert (await use_cases.documents.get(alice, document.id)).id == document.id


async def test_purge_requires_edit_permission(use_cases: UseCases, alice):
    from cyberarche.domain.errors import NotAuthorized
    from cyberarche.domain.memberships import Role

    workspace = await make_workspace(use_cases, alice)
    document = await use_cases.documents.create(
        alice, workspace_id=workspace.id, title="Shared"
    )
    await use_cases.documents.trash(alice, document.id)
    await use_cases.sharing.invite_to_workspace(
        alice, workspace.id, user_id=BOB.user_id, role=Role.COMMENTER
    )

    with pytest.raises(NotAuthorized):
        await use_cases.documents.purge(BOB, document.id)

    # Still in the trash, restorable by an editor.
    restored = await use_cases.documents.restore(alice, document.id)
    assert restored.trashed is False
