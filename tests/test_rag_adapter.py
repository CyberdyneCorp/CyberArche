"""CyberdyneRagAdapter wire-level behavior against a mocked RAG API."""

from __future__ import annotations

import httpx

from cyberarche.adapters.outbound.rag.cyberdyne_rag import CyberdyneRagAdapter
from cyberarche.application.ports.rag import RagQueryMode, RagTaskStatus

BASE = "https://rag.test"


async def token() -> str:
    return "rag-token"


def adapter_with(handler) -> tuple[CyberdyneRagAdapter, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def recording_handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    http = httpx.AsyncClient(transport=httpx.MockTransport(recording_handler))
    return CyberdyneRagAdapter(BASE, http, token), seen


async def test_ensure_project_skips_creation_when_it_exists():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={"slug": "ws-1"})
        raise AssertionError("must not POST when project exists")

    adapter, seen = adapter_with(handler)
    await adapter.ensure_project("ws-1", name="One")
    assert [r.method for r in seen] == ["GET"]
    assert seen[0].headers["authorization"] == "Bearer rag-token"


async def test_ensure_project_creates_when_missing():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(404)
        return httpx.Response(201, json={"slug": "ws-1"})

    adapter, seen = adapter_with(handler)
    await adapter.ensure_project("ws-1", name="One")
    assert [r.method for r in seen] == ["GET", "POST"]


async def test_upload_returns_task_and_poll_maps_status():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/documents/upload"):
            assert b"paper.pdf" in request.read()
            return httpx.Response(200, json={"status": "processing", "task_id": "t-9"})
        if request.url.path.endswith("/tasks/t-9"):
            return httpx.Response(
                200, json={"status": "completed", "error_message": None}
            )
        return httpx.Response(404)

    adapter, _ = adapter_with(handler)
    task = await adapter.upload(
        "ws-1", filename="paper.pdf", content=b"%PDF", content_type="application/pdf"
    )
    assert task.task_id == "t-9"

    polled = await adapter.task_status("ws-1", "t-9")
    assert polled.status is RagTaskStatus.COMPLETED


async def test_query_sends_mode_and_returns_result():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["mode"] == "hybrid"
        assert request.url.params["query"] == "what is arche?"
        return httpx.Response(200, json={"result": "an answer"})

    adapter, _ = adapter_with(handler)
    result = await adapter.query(
        "ws-1", query="what is arche?", mode=RagQueryMode.HYBRID
    )
    assert result == "an answer"
