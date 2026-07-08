"""architecture-quality 12.6: queue-backed ingestion via workers."""

from __future__ import annotations

import pytest

from cyberarche.application.jobs import JobRunner, register_knowledge_jobs
from cyberarche.application.ports.rag import RagTaskStatus
from cyberarche.application.use_cases import UseCases
from cyberarche.application.use_cases.knowledge import blob_key_for
from cyberarche.domain.errors import NotAuthorized


@pytest.fixture
def runner(use_cases: UseCases, task_queue, blobs) -> JobRunner:
    runner = JobRunner(task_queue)
    register_knowledge_jobs(runner, use_cases.knowledge, blobs)
    return runner


async def test_enqueue_does_not_touch_rag_and_worker_completes_it(
    use_cases, rag, blobs, task_queue, runner, alice
):
    workspace = await use_cases.workspaces.create(alice, name="WS")
    rag_uploads_before = dict(rag.projects.get(workspace.rag_project_slug, {}))

    job_id = await use_cases.knowledge.enqueue_ingestion(
        alice, workspace.id, filename="big.pdf", content=b"%PDF huge"
    )

    # Request path: original stored, job queued, RAG untouched.
    assert job_id
    assert rag.projects[workspace.rag_project_slug] == rag_uploads_before
    assert task_queue.pending() == 1
    stored = await blobs.get(blob_key_for(workspace.id, _hash(b"%PDF huge"), "big.pdf"))
    assert stored is not None and stored.content == b"%PDF huge"

    # Worker path: dequeues, uploads to RAG, records the ingestion.
    assert await runner.run_once() is True
    assert "big.pdf" in rag.projects[workspace.rag_project_slug]
    records = await use_cases.knowledge.list_sources(alice, workspace.id)
    assert [r.filename for r in records] == ["big.pdf"]
    assert records[0].status is RagTaskStatus.PROCESSING


async def test_enqueue_requires_editor(use_cases, memberships, clock, alice):
    from cyberarche.domain.memberships import Role, WorkspaceMembership
    from tests.conftest import caller

    viewer = caller("carol", "acme")
    workspace = await use_cases.workspaces.create(alice, name="WS")
    await memberships.add_workspace_member(
        WorkspaceMembership(
            workspace_id=workspace.id,
            user_id=viewer.user_id,
            role=Role.VIEWER,
            granted_at=clock.now(),
        )
    )
    with pytest.raises(NotAuthorized):
        await use_cases.knowledge.enqueue_ingestion(
            viewer, workspace.id, filename="x.txt", content=b"x"
        )


async def test_failed_job_does_not_kill_the_runner(
    use_cases, task_queue, runner, alice
):
    await use_cases.workspaces.create(alice, name="WS")
    await task_queue.enqueue(
        "knowledge.ingest_file",
        {
            "caller": {"user_id": "alice", "tenant_id": "acme"},
            "workspace_id": "nope",
            "filename": "x",
            "blob_key": "missing/blob",
        },
    )
    assert await runner.run_once() is True  # handled (and logged), no raise
    assert await runner.run_once(timeout=0.05) is False  # queue drained


async def test_delete_source_removes_stored_original(use_cases, blobs, alice):
    workspace = await use_cases.workspaces.create(alice, name="WS")
    await use_cases.knowledge.ingest_file(
        alice, workspace.id, filename="notes.md", content=b"# notes"
    )
    key = blob_key_for(workspace.id, _hash(b"# notes"), "notes.md")
    assert await blobs.get(key) is not None

    await use_cases.knowledge.delete_source(alice, workspace.id, filename="notes.md")

    assert await blobs.get(key) is None


def _hash(content: bytes) -> str:
    import hashlib

    return hashlib.sha256(content).hexdigest()
