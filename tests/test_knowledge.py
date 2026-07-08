"""rag-knowledge spec: provisioning, isolation, tracking, dedupe, cascade."""

from __future__ import annotations

import pytest

from cyberarche.application.ports.rag import RagQueryMode, RagTaskStatus
from cyberarche.application.use_cases import UseCases
from cyberarche.application.use_cases.knowledge import project_slug_for
from cyberarche.domain.errors import NotAuthorized


async def test_workspace_creation_provisions_isolated_rag_project(
    use_cases: UseCases, rag, alice
):
    workspace = await use_cases.workspaces.create(alice, name="Research")

    assert workspace.rag_project_slug == project_slug_for(workspace)
    assert workspace.rag_project_slug in rag.projects


async def test_queries_are_scoped_to_the_workspace_project(
    use_cases: UseCases, rag, alice
):
    ws_a = await use_cases.workspaces.create(alice, name="A")
    ws_b = await use_cases.workspaces.create(alice, name="B")
    await use_cases.knowledge.ingest_file(
        alice, ws_a.id, filename="a.txt", content=b"alpha knowledge"
    )

    result_a = await use_cases.knowledge.query(alice, ws_a.id, query="alpha")
    result_b = await use_cases.knowledge.query(alice, ws_b.id, query="alpha")

    assert "a.txt" in result_a
    assert "a.txt" not in result_b  # never leaks across workspaces


async def test_ingestion_tracks_task_to_completion(use_cases: UseCases, alice):
    workspace = await use_cases.workspaces.create(alice, name="Docs")

    record = await use_cases.knowledge.ingest_file(
        alice, workspace.id, filename="paper.pdf", content=b"%PDF-1.7 ..."
    )
    assert record.status is RagTaskStatus.PROCESSING

    refreshed = await use_cases.knowledge.refresh_task(
        alice, workspace.id, record.task_id
    )
    assert refreshed.status is RagTaskStatus.COMPLETED


async def test_duplicate_content_is_not_reingested(use_cases: UseCases, rag, alice):
    workspace = await use_cases.workspaces.create(alice, name="Docs")

    first = await use_cases.knowledge.ingest_file(
        alice, workspace.id, filename="data.csv", content=b"a,b\n1,2"
    )
    second = await use_cases.knowledge.ingest_file(
        alice, workspace.id, filename="data-copy.csv", content=b"a,b\n1,2"
    )

    assert second.task_id == first.task_id  # deduped by content hash
    assert len(rag.tasks[workspace.rag_project_slug]) == 1


async def test_force_reingestion_bypasses_dedupe(use_cases: UseCases, rag, alice):
    workspace = await use_cases.workspaces.create(alice, name="Docs")
    first = await use_cases.knowledge.ingest_file(
        alice, workspace.id, filename="data.csv", content=b"a,b\n1,2"
    )
    forced = await use_cases.knowledge.ingest_file(
        alice, workspace.id, filename="data.csv", content=b"a,b\n1,2", force=True
    )
    assert forced.task_id != first.task_id


async def test_delete_source_cascades_to_rag_datasource(use_cases: UseCases, rag, alice):
    workspace = await use_cases.workspaces.create(alice, name="Docs")
    await use_cases.knowledge.ingest_file(
        alice, workspace.id, filename="notes.md", content=b"# notes"
    )
    assert "notes.md" in rag.projects[workspace.rag_project_slug]

    await use_cases.knowledge.delete_source(alice, workspace.id, filename="notes.md")

    assert "notes.md" not in rag.projects[workspace.rag_project_slug]
    assert await use_cases.knowledge.list_sources(alice, workspace.id) == []


async def test_non_member_cannot_ingest(use_cases: UseCases, alice, bob_other_tenant):
    workspace = await use_cases.workspaces.create(alice, name="Docs")
    from cyberarche.domain.errors import NotFound

    with pytest.raises(NotFound):  # other tenant: workspace invisible
        await use_cases.knowledge.ingest_file(
            bob_other_tenant, workspace.id, filename="x.txt", content=b"x"
        )


async def test_viewer_cannot_ingest_but_can_query(
    use_cases: UseCases, memberships, clock, alice
):
    from tests.conftest import caller
    from cyberarche.domain.memberships import Role, WorkspaceMembership

    viewer = caller("carol", "acme")
    workspace = await use_cases.workspaces.create(alice, name="Docs")
    await memberships.add_workspace_member(
        WorkspaceMembership(
            workspace_id=workspace.id,
            user_id=viewer.user_id,
            role=Role.VIEWER,
            granted_at=clock.now(),
        )
    )

    with pytest.raises(NotAuthorized):
        await use_cases.knowledge.ingest_file(
            viewer, workspace.id, filename="x.txt", content=b"x"
        )
    result = await use_cases.knowledge.query(
        alice, workspace.id, query="anything", mode=RagQueryMode.MIX
    )
    assert "mix" in result


def test_webhook_completes_task_and_requires_secret(api):
    headers = {"Authorization": "Bearer alice-token"}
    workspace = api.post(
        "/api/v1/workspaces", json={"name": "Hooked"}, headers=headers
    ).json()
    record = api.post(
        f"/api/v1/workspaces/{workspace['id']}/knowledge/files",
        files={"file": ("doc.pdf", b"%PDF", "application/pdf")},
        headers=headers,
    ).json()

    # Wrong secret -> 401, status unchanged.
    denied = api.post(
        f"/api/v1/webhooks/rag/{record['task_id']}",
        json={"status": "completed"},
        headers={"x-webhook-secret": "wrong"},
    )
    assert denied.status_code == 401

    accepted = api.post(
        f"/api/v1/webhooks/rag/{record['task_id']}",
        json={"status": "completed"},
        headers={"x-webhook-secret": "hook-secret"},
    )
    assert accepted.status_code == 204

    listed = api.get(
        f"/api/v1/workspaces/{workspace['id']}/knowledge/files", headers=headers
    ).json()
    assert listed[0]["status"] == "completed"
