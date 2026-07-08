"""Shared fixtures: use cases wired to in-memory fakes, plus an HTTP client."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cyberarche.api.bootstrap import create_app
from cyberarche.api.config import Settings
from cyberarche.application.authz import AccessControl
from cyberarche.application.kernel import CallerContext
from cyberarche.application.ports.identity import Claims
from cyberarche.application.testing.fakes import (
    FixedClock,
    InMemoryDocumentRepository,
    InMemoryMembershipRepository,
    InMemorySnapshotRepository,
    InMemoryWorkspaceRepository,
    SequentialIds,
    StaticTokenPort,
)
from cyberarche.application.use_cases import UseCases
from cyberarche.application.use_cases.documents import DocumentUseCases
from cyberarche.application.use_cases.snapshots import SnapshotUseCases
from cyberarche.application.use_cases.workspaces import WorkspaceUseCases
from cyberarche.domain.ids import TenantId, UserId


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock()


@pytest.fixture
def use_cases(clock: FixedClock) -> UseCases:
    workspaces = InMemoryWorkspaceRepository()
    documents = InMemoryDocumentRepository()
    snapshots = InMemorySnapshotRepository()
    memberships = InMemoryMembershipRepository()
    ids = SequentialIds()
    access = AccessControl(memberships)
    return UseCases(
        workspaces=WorkspaceUseCases(workspaces, memberships, clock, ids),
        documents=DocumentUseCases(documents, access, clock, ids),
        snapshots=SnapshotUseCases(snapshots, documents, access, clock, ids),
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
        Settings(backend="memory", auth_base_url=""),
        token_port=StaticTokenPort(dict(TOKENS)),
    )
    with TestClient(app) as client:
        yield client
