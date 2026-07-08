"""Shared fixtures: use cases wired to in-memory fakes, plus an HTTP client."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cyberarche.api.bootstrap import create_app
from cyberarche.api.config import Settings
from cyberarche.application.authz import AccessControl
from cyberarche.application.kernel import CallerContext
from cyberarche.application.ports.identity import Claims
from cyberarche.adapters.outbound.crdt.pycrdt_engine import PycrdtEngine
from cyberarche.application.testing.fakes import (
    FixedClock,
    InMemoryDocumentRepository,
    InMemoryIngestionRepository,
    InMemoryMembershipRepository,
    InMemoryRag,
    InMemorySnapshotRepository,
    InMemoryUpdateLog,
    InMemoryWorkspaceRepository,
    SequentialIds,
    StaticTokenPort,
)
from cyberarche.application.use_cases import UseCases
from cyberarche.application.use_cases.documents import DocumentUseCases
from cyberarche.application.use_cases.knowledge import KnowledgeUseCases
from cyberarche.application.use_cases.realtime import RealtimeUseCases
from cyberarche.application.use_cases.snapshots import SnapshotUseCases
from cyberarche.application.use_cases.workspaces import WorkspaceUseCases
from cyberarche.domain.ids import TenantId, UserId


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock()


@pytest.fixture
def update_log(clock: FixedClock) -> InMemoryUpdateLog:
    return InMemoryUpdateLog(clock)


@pytest.fixture
def memberships() -> InMemoryMembershipRepository:
    return InMemoryMembershipRepository()


@pytest.fixture
def rag() -> InMemoryRag:
    return InMemoryRag()


@pytest.fixture
def use_cases(
    clock: FixedClock,
    update_log: InMemoryUpdateLog,
    memberships: InMemoryMembershipRepository,
    rag: InMemoryRag,
) -> UseCases:
    workspaces = InMemoryWorkspaceRepository()
    documents = InMemoryDocumentRepository()
    snapshots = InMemorySnapshotRepository()
    ingestions = InMemoryIngestionRepository()
    ids = SequentialIds()
    access = AccessControl(memberships)
    return UseCases(
        workspaces=WorkspaceUseCases(workspaces, memberships, clock, ids, rag),
        documents=DocumentUseCases(documents, access, clock, ids),
        snapshots=SnapshotUseCases(snapshots, documents, access, clock, ids),
        realtime=RealtimeUseCases(documents, update_log, PycrdtEngine(), access),
        knowledge=KnowledgeUseCases(workspaces, ingestions, rag, access, clock),
    )


def caller(user: str = "alice", tenant: str = "acme") -> CallerContext:
    return CallerContext(user_id=UserId(user), tenant_id=TenantId(tenant))


@pytest.fixture
def alice() -> CallerContext:
    return caller("alice", "acme")


@pytest.fixture
def bob_other_tenant() -> CallerContext:
    return caller("bob", "globex")


# ---- HTTP surface ----------------------------------------------------------

TOKENS = {
    "alice-token": Claims(subject="alice", tenant_id="acme", email="alice@acme.test"),
    "mallory-token": Claims(subject="mallory", tenant_id="globex"),
}


@pytest.fixture
def api() -> TestClient:
    app = create_app(
        Settings(
            backend="memory",
            auth_base_url="",
            rag_base_url="",
            rag_webhook_secret="hook-secret",
        ),
        token_port=StaticTokenPort(dict(TOKENS)),
    )
    with TestClient(app) as client:
        yield client
