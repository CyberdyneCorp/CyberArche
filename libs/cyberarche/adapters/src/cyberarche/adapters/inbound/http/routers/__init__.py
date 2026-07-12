"""All HTTP routers. Routers are thin: parse -> delegate to use case -> DTO."""

from __future__ import annotations

from cyberarche.adapters.inbound.http.routers.agent import router as agent_router
from cyberarche.adapters.inbound.http.routers.agent_persona import (
    router as agent_persona_router,
)
from cyberarche.adapters.inbound.http.routers.agent_skills import (
    router as agent_skills_router,
)
from cyberarche.adapters.inbound.http.routers.api_keys import router as api_keys_router
from cyberarche.adapters.inbound.http.routers.auth import router as auth_router
from cyberarche.adapters.inbound.http.routers.connectors import (
    router as connectors_router,
)
from cyberarche.adapters.inbound.http.routers.documents import router as documents_router
from cyberarche.adapters.inbound.http.routers.files import router as files_router
from cyberarche.adapters.inbound.http.routers.folders import router as folders_router
from cyberarche.adapters.inbound.http.routers.google import router as google_router
from cyberarche.adapters.inbound.http.routers.health import router as health_router
from cyberarche.adapters.inbound.http.routers.knowledge import (
    router as knowledge_router,
    webhook_router,
)
from cyberarche.adapters.inbound.http.routers.notifications import (
    router as notifications_router,
)
from cyberarche.adapters.inbound.http.routers.scheduled_agents import (
    router as scheduled_agents_router,
)
from cyberarche.adapters.inbound.http.routers.sharing import router as sharing_router
from cyberarche.adapters.inbound.http.routers.teamspaces import router as teamspaces_router
from cyberarche.adapters.inbound.http.routers.templates import router as templates_router
from cyberarche.adapters.inbound.http.routers.workspaces import router as workspaces_router

all_routers = [
    health_router,
    auth_router,
    api_keys_router,
    workspaces_router,
    documents_router,
    knowledge_router,
    webhook_router,
    agent_router,
    agent_persona_router,
    agent_skills_router,
    scheduled_agents_router,
    google_router,
    connectors_router,
    sharing_router,
    teamspaces_router,
    folders_router,
    files_router,
    notifications_router,
    templates_router,
]
