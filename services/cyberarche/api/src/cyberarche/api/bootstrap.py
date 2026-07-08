"""FastAPI application factory.

Request path: auth dependency (401 seam) -> router -> use case -> DomainError seam.
The Container is built once per process and shared via app.state (stateless
service otherwise — architecture-quality spec).
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cyberarche.adapters.inbound.http.errors import install_error_handlers
from cyberarche.adapters.inbound.http.routers import all_routers
from cyberarche.adapters.wiring import build_container
from cyberarche.api.config import Settings
from cyberarche.api.observability import install_observability
from cyberarche.application.ports.identity import TokenPort


def create_app(
    settings: Settings | None = None, *, token_port: TokenPort | None = None
) -> FastAPI:
    """`token_port` is injectable for tests and the dockerless sample runtime."""
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        container = await build_container(settings.wiring(), token_port=token_port)
        app.state.container = container
        try:
            yield
        finally:
            await container.aclose()

    app = FastAPI(title="CyberArche API", version="0.1.0", lifespan=lifespan)
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
    return app
