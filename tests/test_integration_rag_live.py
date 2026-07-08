"""Live CyberdyneRAG integration pass (env-gated, skipped by default).

Requires:
  CYBERARCHE_IT_AUTH_URL / CYBERARCHE_IT_EMAIL / CYBERARCHE_IT_PASSWORD
  CYBERARCHE_IT_RAG_URL   CyberdyneRAG base URL

The RAG service accepts CyberdyneAuth bearer tokens; the pass logs in,
drives our real CyberdyneRagAdapter end-to-end against a dedicated
test project, and hard-deletes the project afterwards. Existing projects
are never touched.
"""

from __future__ import annotations

import asyncio
import os
import uuid

import httpx
import pytest

from cyberarche.adapters.outbound.rag.cyberdyne_rag import CyberdyneRagAdapter
from cyberarche.application.ports.rag import RagQueryMode, RagTaskStatus

REQUIRED = (
    "CYBERARCHE_IT_AUTH_URL",
    "CYBERARCHE_IT_EMAIL",
    "CYBERARCHE_IT_PASSWORD",
    "CYBERARCHE_IT_RAG_URL",
)

pytestmark = pytest.mark.skipif(
    any(not os.environ.get(name) for name in REQUIRED),
    reason="live RAG integration env (CYBERARCHE_IT_*) not configured",
)

POLL_TIMEOUT_SECONDS = 90.0
CONTENT = (
    b"CyberArche is an AI-centric collaborative document platform. "
    b"Its whiteboard block is Excalidraw-style and supports mind maps."
)


@pytest.fixture(scope="module")
def live_token() -> str:
    response = httpx.post(
        f"{os.environ['CYBERARCHE_IT_AUTH_URL'].rstrip('/')}/api/v1/auth/login",
        json={
            "email": os.environ["CYBERARCHE_IT_EMAIL"],
            "password": os.environ["CYBERARCHE_IT_PASSWORD"],
        },
        timeout=15.0,
    )
    response.raise_for_status()
    return response.json()["access_token"]


@pytest.fixture
async def rag_live(live_token):
    """(adapter, slug): a real adapter bound to a disposable test project."""
    base_url = os.environ["CYBERARCHE_IT_RAG_URL"]
    slug = f"cyberarche-it-{uuid.uuid4().hex[:8]}"

    async def token() -> str:
        return live_token

    async with httpx.AsyncClient(timeout=30.0) as http:
        adapter = CyberdyneRagAdapter(base_url, http, token)
        try:
            yield adapter, slug
        finally:  # always hard-delete the disposable project
            await http.delete(
                f"{base_url.rstrip('/')}/api/v1/projects/{slug}",
                params={"hard_delete": "true"},
                headers={"Authorization": f"Bearer {live_token}"},
            )


async def wait_for_completion(adapter, slug: str, task_id: str) -> RagTaskStatus:
    deadline = asyncio.get_event_loop().time() + POLL_TIMEOUT_SECONDS
    while asyncio.get_event_loop().time() < deadline:
        task = await adapter.task_status(slug, task_id)
        if task.status in (RagTaskStatus.COMPLETED, RagTaskStatus.FAILED):
            return task.status
        await asyncio.sleep(3.0)
    return task.status


async def test_live_rag_full_lifecycle(rag_live):
    adapter, slug = rag_live

    # ensure_project: creates when missing, idempotent when present.
    await adapter.ensure_project(slug, name="CyberArche IT")
    await adapter.ensure_project(slug, name="CyberArche IT")

    # upload -> task -> completed.
    task = await adapter.upload(
        slug, filename="facts.txt", content=CONTENT, content_type="text/plain"
    )
    assert task.task_id
    status = await wait_for_completion(adapter, slug, task.task_id)
    assert status is RagTaskStatus.COMPLETED

    # retrieval, grounded in the ingested content.
    answer = await adapter.query(
        slug,
        query="What style is CyberArche's whiteboard block?",
        mode=RagQueryMode.HYBRID,
    )
    assert "excalidraw" in answer.lower()

    # delete-datasource cascade.
    await adapter.delete_datasource(slug, "facts.txt")


async def test_live_knowledge_use_case_flow_against_real_rag(rag_live):
    """The full application flow (provision -> ingest -> track -> query)
    over the live service, exactly as the API would run it."""
    from cyberarche.application.authz import AccessControl
    from cyberarche.application.testing.fakes import (
        FixedClock,
        InMemoryIngestionRepository,
        InMemoryMembershipRepository,
        InMemoryWorkspaceRepository,
        SequentialIds,
    )
    from cyberarche.application.use_cases.knowledge import KnowledgeUseCases
    from cyberarche.application.use_cases.workspaces import WorkspaceUseCases
    from cyberarche.application.ports.rag import RagQueryMode
    from tests.conftest import caller

    adapter, slug = rag_live
    clock, ids = FixedClock(), SequentialIds()
    workspaces = InMemoryWorkspaceRepository()
    memberships = InMemoryMembershipRepository()
    access = AccessControl(memberships)
    knowledge = KnowledgeUseCases(
        workspaces, InMemoryIngestionRepository(), adapter, access, clock
    )
    alice = caller("it-alice", "it-acme")

    # rag=None: creation must not auto-provision a ws-<id> project that the
    # fixture's cleanup would not own. The workspace points at the
    # disposable slug instead; provisioning happens on first ingest.
    workspace = await WorkspaceUseCases(
        workspaces, memberships, clock, ids, None
    ).create(alice, name="Live RAG WS")
    workspaces._items[workspace.id] = workspace.with_rag_project(slug)

    record = await knowledge.ingest_file(
        alice, workspace.id, filename="facts.txt", content=CONTENT,
        content_type="text/plain",
    )
    deadline = asyncio.get_event_loop().time() + POLL_TIMEOUT_SECONDS
    while asyncio.get_event_loop().time() < deadline:
        record = await knowledge.refresh_task(alice, workspace.id, record.task_id)
        if record.status in (RagTaskStatus.COMPLETED, RagTaskStatus.FAILED):
            break
        await asyncio.sleep(3.0)
    assert record.status is RagTaskStatus.COMPLETED

    answer = await knowledge.query(
        alice, workspace.id, query="What kind of platform is CyberArche?",
        mode=RagQueryMode.HYBRID,
    )
    assert "cyberarche" in answer.lower()

    await knowledge.delete_source(alice, workspace.id, filename="facts.txt")
    assert await knowledge.list_sources(alice, workspace.id) == []