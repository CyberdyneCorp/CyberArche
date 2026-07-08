"""document-model spec: snapshot list/restore scenarios.

One test per scenario in the "Version snapshots" requirement. The previous
suite asserted only `restored.content` — the *new snapshot row's* content,
copied verbatim by record() — and so passed against a restore that never
touched the document. Every test here reads the document back.
"""

from __future__ import annotations

import pytest

from cyberarche.adapters.outbound.crdt.pycrdt_engine import PycrdtEngine
from cyberarche.application.use_cases import UseCases
from cyberarche.domain.errors import NotAuthorized, NotFound
from cyberarche.domain.ids import SnapshotId
from cyberarche.domain.memberships import Role
from tests.conftest import caller

BOB = caller("bob", "acme")


def block(block_id: str, text: str) -> dict:
    return {"id": block_id, "type": "paragraph", "data": {"text": text}}


async def blocks_of(use_cases: UseCases, actor, document_id) -> list[dict]:
    """The document's live content, as any reader would see it."""
    state = await use_cases.realtime.current_state(actor, document_id)
    return PycrdtEngine().read_blocks(state)


async def setup(use_cases: UseCases, alice):
    workspace = await use_cases.workspaces.create(alice, name="Docs")
    document = await use_cases.documents.create(
        alice, workspace_id=workspace.id, title="Doc"
    )
    return workspace, document


async def snapshot_of_now(use_cases: UseCases, alice, document_id, sv: bytes):
    return await use_cases.snapshots.record(
        alice,
        document_id,
        content={"blocks": await blocks_of(use_cases, alice, document_id)},
        state_vector=sv,
    )


async def test_restore_replaces_the_live_document_content(use_cases: UseCases, alice):
    _, document = await setup(use_cases, alice)
    await use_cases.agent.apply_blocks(alice, document.id, [block("b1", "first")])
    v1 = await snapshot_of_now(use_cases, alice, document.id, b"sv1")

    # Move the document on: b1 is gone, b2 is new.
    await use_cases.agent.delete_block(alice, document.id, "b1")
    await use_cases.agent.apply_blocks(alice, document.id, [block("b2", "second")])
    assert [b["id"] for b in await blocks_of(use_cases, alice, document.id)] == ["b2"]

    await use_cases.snapshots.restore(alice, document.id, v1.id)

    live = await blocks_of(use_cases, alice, document.id)
    assert [b["id"] for b in live] == ["b1"]
    assert live[0]["data"]["text"] == "first"


async def test_restore_is_applied_through_the_crdt_update_log(
    use_cases: UseCases, alice, update_log
):
    _, document = await setup(use_cases, alice)
    await use_cases.agent.apply_blocks(alice, document.id, [block("b1", "first")])
    v1 = await snapshot_of_now(use_cases, alice, document.id, b"sv1")
    await use_cases.agent.apply_blocks(alice, document.id, [block("b2", "second")])
    before = len(await update_log.list_for_document(document.id))

    await use_cases.snapshots.restore(alice, document.id, v1.id)

    entries = await update_log.list_for_document(document.id)
    assert len(entries) == before + 1  # the restore is an ordinary update
    assert entries[-1].origin == "restore:alice"  # attributed


async def test_restore_records_a_new_snapshot_pointing_at_the_source(
    use_cases: UseCases, alice
):
    _, document = await setup(use_cases, alice)
    await use_cases.agent.apply_blocks(alice, document.id, [block("b1", "first")])
    v1 = await snapshot_of_now(use_cases, alice, document.id, b"sv1")
    await snapshot_of_now(use_cases, alice, document.id, b"sv2")

    restored = await use_cases.snapshots.restore(alice, document.id, v1.id)

    assert restored.restored_from == v1.id
    history = await use_cases.snapshots.list(alice, document.id)
    assert [s.seq for s in history] == [1, 2, 3]  # history stays append-only


async def test_blocks_surviving_a_restore_keep_their_identity(
    use_cases: UseCases, alice
):
    _, document = await setup(use_cases, alice)
    await use_cases.agent.apply_blocks(alice, document.id, [block("b1", "first")])
    v1 = await snapshot_of_now(use_cases, alice, document.id, b"sv1")

    # b1 survives into the current version, edited; a comment anchors to it.
    await use_cases.agent.update_block(alice, document.id, "b1", {"text": "edited"})
    comment = await use_cases.sharing.add_comment(
        alice, document.id, block_id="b1", body="anchored here"
    )

    await use_cases.snapshots.restore(alice, document.id, v1.id)

    live = await blocks_of(use_cases, alice, document.id)
    assert [b["id"] for b in live] == ["b1"]  # not re-created under a new id
    assert live[0]["data"]["text"] == "first"
    comments = await use_cases.sharing.list_comments(alice, document.id)
    assert [c.block_id for c in comments] == [comment.block_id]


async def test_restoring_the_same_snapshot_twice_is_idempotent(
    use_cases: UseCases, alice, update_log
):
    _, document = await setup(use_cases, alice)
    await use_cases.agent.apply_blocks(alice, document.id, [block("b1", "first")])
    v1 = await snapshot_of_now(use_cases, alice, document.id, b"sv1")
    await use_cases.agent.apply_blocks(alice, document.id, [block("b2", "second")])

    await use_cases.snapshots.restore(alice, document.id, v1.id)
    after_first = await blocks_of(use_cases, alice, document.id)
    entries = len(await update_log.list_for_document(document.id))

    await use_cases.snapshots.restore(alice, document.id, v1.id)

    assert await blocks_of(use_cases, alice, document.id) == after_first
    # D-5: the second restore changes nothing, so it appends no empty update.
    assert len(await update_log.list_for_document(document.id)) == entries


async def test_a_commenter_may_not_restore(use_cases: UseCases, alice):
    workspace, document = await setup(use_cases, alice)
    await use_cases.agent.apply_blocks(alice, document.id, [block("b1", "first")])
    v1 = await snapshot_of_now(use_cases, alice, document.id, b"sv1")
    await use_cases.agent.apply_blocks(alice, document.id, [block("b2", "second")])
    await use_cases.sharing.invite_to_workspace(
        alice, workspace.id, user_id=BOB.user_id, role=Role.COMMENTER
    )

    with pytest.raises(NotAuthorized):
        await use_cases.snapshots.restore(BOB, document.id, v1.id)

    live = await blocks_of(use_cases, alice, document.id)
    assert [b["id"] for b in live] == ["b1", "b2"]  # unchanged


async def test_restoring_an_unknown_snapshot_fails(use_cases: UseCases, alice):
    _, document = await setup(use_cases, alice)

    with pytest.raises(NotFound):
        await use_cases.snapshots.restore(alice, document.id, SnapshotId("nope"))
