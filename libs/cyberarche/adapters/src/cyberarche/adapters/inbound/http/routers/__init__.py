"""All HTTP routers. Routers are thin: parse -> delegate to use case -> DTO."""

from __future__ import annotations

from cyberarche.adapters.inbound.http.routers.agent import router as agent_router
from cyberarche.adapters.inbound.http.routers.auth import router as auth_router
from cyberarche.adapters.inbound.http.routers.connectors import (
    router as connectors_router,
)
from cyberarche.adapters.inbound.http.routers.documents import router as documents_router
from cyberarche.adapters.inbound.http.routers.health import router as health_router
from cyberarche.adapters.inbound.http.routers.knowledge import (
    router as knowledge_router,
    webhook_router,
)
from cyberarche.adapters.inbound.http.routers.sharing import router as sharing_router
from cyberarche.adapters.inbound.http.routers.workspaces import router as workspaces_router

all_routers = [
    health_router,
    auth_router,
    workspaces_router,
    documents_router,
    knowledge_router,
    webhook_router,
    agent_router,
    connectors_router,
    sharing_router,
]
