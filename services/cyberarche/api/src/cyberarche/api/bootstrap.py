"""FastAPI application factory.

Request path: auth dependency (401 seam) -> router -> use case -> DomainError seam.
The Container is built once per process and shared via app.state (stateless
service otherwise — architecture-quality spec).
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cyberarche.adapters.inbound.http.errors import install_error_handlers
from cyberarche.adapters.inbound.http.realtime import DocumentPeers
from cyberarche.adapters.inbound.http.realtime import router as realtime_router
from cyberarche.adapters.inbound.http.routers import all_routers
from cyberarche.adapters.wiring import Container, build_container
from cyberarche.api.config import Settings
from cyberarche.api.observability import install_observability
from cyberarche.api.security_middleware import (
    AuthRateLimitMiddleware,
    SecurityHeadersMiddleware,
)
from cyberarche.application.ports.identity import TokenPort

logger = logging.getLogger(__name__)


async def _run_scheduler(container: Container, interval: int) -> None:
    """Tick the autonomous-agent scheduler forever; a failing tick is logged and
    does not stop the loop."""
    while True:
        await asyncio.sleep(interval)
        try:
            await container.use_cases.scheduled_agents.run_due()
        except Exception:  # a bad tick must never kill the scheduler
            logger.exception("scheduled-agent tick failed")


async def _run_digest_scheduler(container: Container, interval: int) -> None:
    """Tick the email-digest scheduler forever; a failing tick is logged and
    does not stop the loop."""
    while True:
        await asyncio.sleep(interval)
        try:
            await container.use_cases.notification_digest.run_due(datetime.now(UTC))
        except Exception:  # a bad tick must never kill the scheduler
            logger.exception("notification-digest tick failed")


def _start_schedulers(active: Container, settings: Settings) -> list[asyncio.Task]:
    """The in-process background schedulers for the real (postgres) deployment.
    The memory backend (tests/local) has no persistent state and none run."""
    tasks: list[asyncio.Task] = []
    if settings.backend != "postgres":
        return tasks
    if settings.enable_scheduler:
        tasks.append(
            asyncio.create_task(
                _run_scheduler(active, settings.scheduler_interval_seconds)
            )
        )
    if settings.enable_digest:
        tasks.append(
            asyncio.create_task(
                _run_digest_scheduler(active, settings.digest_interval_seconds)
            )
        )
    return tasks


async def _stop_schedulers(tasks: list[asyncio.Task]) -> None:
    for task in tasks:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


def create_app(
    settings: Settings | None = None,
    *,
    token_port: TokenPort | None = None,
    container: Container | None = None,
) -> FastAPI:
    """`token_port` is injectable for tests and the dockerless sample runtime.
    Passing a pre-built `container` lets several app instances share one
    (multi-replica tests over a shared bus/store)."""
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        owned = container is None
        active = container or await build_container(
            settings.wiring(), token_port=token_port
        )
        app.state.container = active
        # Local socket registry bridged to the shared peer bus (12.5).
        app.state.document_peers = DocumentPeers(active.peer_bus)
        # Autonomous agents + the email digest run on in-process schedulers, only
        # in the real (postgres) deployment — the memory backend (tests/local)
        # has no persistent state and starts none.
        schedulers = _start_schedulers(active, settings)
        try:
            yield
        finally:
            await _stop_schedulers(schedulers)
            if owned:
                await active.aclose()

    app = FastAPI(title="CyberArche API", version="0.1.0", lifespan=lifespan)
    # A credentialed wildcard origin would let any site read authenticated
    # responses — refuse it at startup rather than boot insecure (audit INFO-1).
    if "*" in settings.cors_origins:
        raise ValueError(
            "CYBERARCHE_CORS_ORIGINS must not be '*' when credentials are allowed"
        )
    # Middleware runs outermost-last-added. Add the rate limiter and security
    # headers FIRST, then CORS, so CORS is the OUTERMOST layer and its
    # Access-Control-Allow-Origin header is attached even to a short-circuited
    # 429 from the rate limiter — otherwise the browser reports a CORS failure
    # instead of the real 429 (regression from the audit hardening).
    app.add_middleware(AuthRateLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_observability(app)
    install_error_handlers(app)
    for router in all_routers:
        app.include_router(router)
    app.include_router(realtime_router)
    return app
