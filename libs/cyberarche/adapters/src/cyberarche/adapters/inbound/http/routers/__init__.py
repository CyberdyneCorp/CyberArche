"""All HTTP routers. Routers are thin: parse -> delegate to use case -> DTO."""

from __future__ import annotations

from cyberarche.adapters.inbound.http.routers.documents import router as documents_router
from cyberarche.adapters.inbound.http.routers.health import router as health_router
from cyberarche.adapters.inbound.http.routers.workspaces import router as workspaces_router

all_routers = [health_router, workspaces_router, documents_router]
