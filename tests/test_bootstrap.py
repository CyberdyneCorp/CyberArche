"""API bootstrap: container ownership, autonomous-agent scheduler, CORS."""

from __future__ import annotations

import asyncio
import threading
from contextlib import suppress
from types import SimpleNamespace

import anyio
from fastapi.testclient import TestClient

from cyberarche.adapters.wiring import Container, WiringConfig, build_container
from cyberarche.api.bootstrap import _run_scheduler, create_app
from cyberarche.api.config import Settings
from cyberarche.application.testing.fakes import StaticTokenPort
from tests.conftest import TOKENS


def auth(token: str = "alice-token") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def settings(**overrides) -> Settings:
    base = {"backend": "memory", "auth_base_url": "", "rag_base_url": ""}
    return Settings(**{**base, **overrides})


def build_shared_container() -> Container:
    async def build():
        return await build_container(
            WiringConfig(backend="memory"), token_port=StaticTokenPort(dict(TOKENS))
        )

    return anyio.run(build)


# ---- scheduler loop ---------------------------------------------------------


class TickingAgents:
    """Stands in for ScheduledAgentUseCases; the first tick fails."""

    def __init__(self) -> None:
        self.calls = 0
        self.succeeded = asyncio.Event()

    async def run_due(self) -> None:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("boom")
        self.succeeded.set()


async def test_scheduler_loop_survives_a_failing_tick():
    """A bad tick is logged and must never kill the scheduler."""
    agents = TickingAgents()
    container = SimpleNamespace(use_cases=SimpleNamespace(scheduled_agents=agents))
    task = asyncio.create_task(_run_scheduler(container, 0))
    try:
        await asyncio.wait_for(agents.succeeded.wait(), timeout=2)
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
    assert agents.calls >= 2


def test_postgres_deployment_ticks_the_scheduler(monkeypatch):
    """With the postgres backend the lifespan starts the scheduler, and app
    shutdown cancels it (the `with` block exiting proves cancellation)."""
    container = build_shared_container()
    ticked = threading.Event()

    async def run_due() -> None:
        ticked.set()

    monkeypatch.setattr(container.use_cases.scheduled_agents, "run_due", run_due)
    app = create_app(
        settings(backend="postgres", scheduler_interval_seconds=0),
        container=container,
    )
    with TestClient(app):
        assert ticked.wait(timeout=2)
    anyio.run(container.aclose)


def test_scheduler_not_started_when_disabled_or_on_memory_backend(monkeypatch):
    container = build_shared_container()
    ticked = threading.Event()

    async def run_due() -> None:
        ticked.set()

    monkeypatch.setattr(container.use_cases.scheduled_agents, "run_due", run_due)
    for overrides in (
        {"backend": "postgres", "enable_scheduler": False},
        {"backend": "memory", "enable_scheduler": True},
    ):
        app = create_app(
            settings(scheduler_interval_seconds=0, **overrides), container=container
        )
        with TestClient(app):
            assert not ticked.wait(timeout=0.2)
    anyio.run(container.aclose)


# ---- container ownership ----------------------------------------------------


def _spy_on_aclose(monkeypatch) -> list[Container]:
    closed: list[Container] = []
    original = Container.aclose

    async def spy(self: Container) -> None:
        closed.append(self)
        await original(self)

    monkeypatch.setattr(Container, "aclose", spy)
    return closed


def test_owned_container_is_closed_on_shutdown(monkeypatch):
    closed = _spy_on_aclose(monkeypatch)
    app = create_app(settings(), token_port=StaticTokenPort(dict(TOKENS)))

    with TestClient(app) as client:
        assert client.get("/api/v1/workspaces", headers=auth()).json() == []
        active = app.state.container
    assert closed == [active]


def test_shared_container_survives_app_shutdown(monkeypatch):
    """A pre-built container (multi-replica setups) is not closed by any
    single app instance shutting down."""
    closed = _spy_on_aclose(monkeypatch)
    container = build_shared_container()
    app = create_app(settings(), container=container)

    with TestClient(app) as client:
        assert app.state.container is container
        assert client.get("/api/v1/workspaces", headers=auth()).json() == []
    assert closed == []
    anyio.run(container.aclose)


# ---- CORS -------------------------------------------------------------------


def test_cors_preflight_allows_configured_origin():
    app = create_app(
        settings(cors_origins=["http://app.test"]),
        token_port=StaticTokenPort(dict(TOKENS)),
    )
    with TestClient(app) as client:
        response = client.options(
            "/api/v1/workspaces",
            headers={
                "Origin": "http://app.test",
                "Access-Control-Request-Method": "GET",
            },
        )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://app.test"
    assert response.headers["access-control-allow-credentials"] == "true"
