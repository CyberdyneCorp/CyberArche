"""document-model spec: snapshot list/restore scenarios."""

from __future__ import annotations

from cyberarche.application.use_cases import UseCases


async def test_restore_replaces_content_and_records_new_snapshot(
    use_cases: UseCases, alice
):
    workspace = await use_cases.workspaces.create(alice, name="Docs")
    document = await use_cases.documents.create(
        alice, workspace_id=workspace.id, title="Doc"
    )

    v1 = await use_cases.snapshots.record(
        alice, document.id, content={"blocks": ["v1"]}, state_vector=b"sv1"
    )
    await use_cases.snapshots.record(
        alice, document.id, content={"blocks": ["v2"]}, state_vector=b"sv2"
    )

    restored = await use_cases.snapshots.restore(alice, document.id, v1.id)

    assert restored.content == {"blocks": ["v1"]}
    assert restored.restored_from == v1.id
    history = await use_cases.snapshots.list(alice, document.id)
    assert [s.seq for s in history] == [1, 2, 3]
