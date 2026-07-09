"""realtime-collaboration spec: convergence, catch-up, restart, permissions."""

from __future__ import annotations

import pytest
from pycrdt import Doc, Text

from cyberarche.adapters.outbound.crdt.pycrdt_engine import PycrdtEngine
from cyberarche.application.authz import AccessControl
from cyberarche.application.use_cases import UseCases
from cyberarche.application.use_cases.realtime import RealtimeUseCases
from cyberarche.domain.errors import NotAuthorized
from cyberarche.domain.memberships import Role, WorkspaceMembership


def text_of(state: bytes) -> str:
    doc = Doc()
    if state:
        doc.apply_update(state)
    return str(doc.get("text", type=Text))


def edit(state: bytes, insert: str, index: int = 0) -> bytes:
    """Produce the incremental update a client would send for one edit."""
    doc = Doc()
    if state:
        doc.apply_update(state)
    before = doc.get_state()
    text = doc.get("text", type=Text)
    text.insert(index, insert)
    return doc.get_update(before)


async def setup_document(use_cases: UseCases, alice):
    workspace = await use_cases.workspaces.create(alice, name="Docs")
    teamspace = await use_cases.teamspaces.create(alice, workspace.id, name="Team")
    document = await use_cases.documents.create(
        alice, workspace_id=workspace.id, title="Doc", teamspace_id=teamspace.id
    )
    return workspace, document


async def join_as_member(use_cases, memberships, clock, workspace, user, role: Role):
    await memberships.add_workspace_member(
        WorkspaceMembership(
            workspace_id=workspace.id, user_id=user.user_id, role=role,
            granted_at=clock.now(),
        )
    )


async def test_two_editors_converge(use_cases: UseCases, memberships, clock, alice):
    from tests.conftest import caller

    bob = caller("bob", "acme")
    workspace, document = await setup_document(use_cases, alice)
    await join_as_member(use_cases, memberships, clock, workspace, bob, Role.EDITOR)

    # Both start from the same state and edit concurrently.
    _, base = await use_cases.realtime.join(alice, document.id)
    await use_cases.realtime.apply(alice, document.id, edit(base, "alice:"))
    await use_cases.realtime.apply(bob, document.id, edit(base, "bob:"))

    state_alice = await use_cases.realtime.current_state(alice, document.id)
    state_bob = await use_cases.realtime.current_state(bob, document.id)
    assert state_alice == state_bob
    merged = text_of(state_alice)
    assert "alice:" in merged and "bob:" in merged


async def test_late_joiner_receives_current_state(
    use_cases: UseCases, memberships, clock, alice
):
    from tests.conftest import caller

    bob = caller("bob", "acme")
    workspace, document = await setup_document(use_cases, alice)
    await join_as_member(use_cases, memberships, clock, workspace, bob, Role.VIEWER)

    _, base = await use_cases.realtime.join(alice, document.id)
    await use_cases.realtime.apply(alice, document.id, edit(base, "early content"))

    _, late_state = await use_cases.realtime.join(bob, document.id)
    assert text_of(late_state) == "early content"


async def test_reconstruct_after_restart(
    use_cases: UseCases, update_log, memberships, alice
):
    _, document = await setup_document(use_cases, alice)
    _, base = await use_cases.realtime.join(alice, document.id)
    await use_cases.realtime.apply(alice, document.id, edit(base, "durable"))

    # "Restart": a fresh use-case instance over the same persisted log.
    restarted = RealtimeUseCases(
        use_cases.documents._documents,
        update_log,
        PycrdtEngine(),
        AccessControl(memberships),
    )
    _, state = await restarted.join(alice, document.id)
    assert text_of(state) == "durable"


async def test_viewer_update_is_rejected(use_cases: UseCases, memberships, clock, alice):
    from tests.conftest import caller

    viewer = caller("carol", "acme")
    workspace, document = await setup_document(use_cases, alice)
    await join_as_member(use_cases, memberships, clock, workspace, viewer, Role.VIEWER)

    _, state = await use_cases.realtime.join(viewer, document.id)  # can join
    with pytest.raises(NotAuthorized):
        await use_cases.realtime.apply(viewer, document.id, edit(state, "sneaky"))
    assert text_of(await use_cases.realtime.current_state(alice, document.id)) == ""


async def test_offline_edits_merge_on_reconnect(use_cases: UseCases, alice):
    _, document = await setup_document(use_cases, alice)
    _, base = await use_cases.realtime.join(alice, document.id)

    # Client goes offline at `base`; others keep editing meanwhile.
    await use_cases.realtime.apply(alice, document.id, edit(base, "online "))

    # Offline client batches edits against its stale local copy...
    offline_update = edit(base, "offline ")
    # ...and reconnects: the stale-based update still merges conflict-free.
    await use_cases.realtime.apply(alice, document.id, offline_update)

    merged = text_of(await use_cases.realtime.current_state(alice, document.id))
    assert "online " in merged and "offline " in merged


async def test_compaction_preserves_content_and_records_snapshot(
    use_cases: UseCases, update_log, snapshots_repo, alice
):
    from cyberarche.application.use_cases import realtime as realtime_module

    _, document = await setup_document(use_cases, alice)
    state = b""
    for i in range(realtime_module.COMPACTION_THRESHOLD + 5):
        update = edit(state, f"{i},")
        await use_cases.realtime.apply(alice, document.id, update)
        state = await use_cases.realtime.current_state(alice, document.id)

    count = await update_log.count(document.id)
    assert count < realtime_module.COMPACTION_THRESHOLD  # log was compacted
    assert "0," in text_of(state) and "204," in text_of(state)

    # Compaction also recorded a server-initiated content snapshot
    # (document-model spec: periodic snapshots).
    auto_snapshot = await snapshots_repo.latest(document.id)
    assert auto_snapshot is not None
    assert "blocks" in auto_snapshot.content
    assert auto_snapshot.state_vector  # reconstructable checkpoint
