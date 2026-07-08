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
from cyberarche.adapters.outbound.extraction.files import FileExtractor
from cyberarche.application.testing.fakes import (
    FakeMcpClient,
    FixedClock,
    InMemoryAgentRunRepository,
    InMemoryApiKeyRepository,
    InMemoryBlobStorage,
    InMemoryCommentRepository,
    InMemoryConnectorRepository,
    InMemoryDocumentRepository,
    InMemoryIngestionRepository,
    InMemoryMembershipRepository,
    InMemoryRag,
    InMemoryShareLinkRepository,
    InMemorySnapshotRepository,
    InMemoryTaskQueue,
    InMemoryUpdateLog,
    InMemoryWorkspaceRepository,
    NaiveSecretBox,
    ScriptedLLM,
    SequentialIds,
    StaticTokenPort,
)
from cyberarche.application.use_cases import UseCases
from cyberarche.application.use_cases.agent import AgentUseCases
from cyberarche.application.use_cases.api_keys import ApiKeyUseCases
from cyberarche.application.use_cases.connectors import ConnectorUseCases
from cyberarche.application.use_cases.documents import DocumentUseCases
from cyberarche.application.use_cases.knowledge import KnowledgeUseCases
from cyberarche.application.use_cases.realtime import RealtimeUseCases
from cyberarche.application.use_cases.sharing import SharingUseCases
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
def llm() -> ScriptedLLM:
    return ScriptedLLM([])


@pytest.fixture
def agent_runs() -> InMemoryAgentRunRepository:
    return InMemoryAgentRunRepository()


@pytest.fixture
def mcp_client() -> FakeMcpClient:
    return FakeMcpClient()


@pytest.fixture
def secret_box() -> NaiveSecretBox:
    return NaiveSecretBox()


@pytest.fixture
def connector_repo() -> InMemoryConnectorRepository:
    return InMemoryConnectorRepository()


@pytest.fixture
def blobs() -> InMemoryBlobStorage:
    return InMemoryBlobStorage()


@pytest.fixture
def task_queue() -> InMemoryTaskQueue:
    return InMemoryTaskQueue()


@pytest.fixture
def snapshots_repo() -> InMemorySnapshotRepository:
    return InMemorySnapshotRepository()


@pytest.fixture
def use_cases(
    clock: FixedClock,
    update_log: InMemoryUpdateLog,
    memberships: InMemoryMembershipRepository,
    rag: InMemoryRag,
    llm: ScriptedLLM,
    agent_runs: InMemoryAgentRunRepository,
    mcp_client: FakeMcpClient,
    secret_box: NaiveSecretBox,
    connector_repo: InMemoryConnectorRepository,
    blobs: InMemoryBlobStorage,
    task_queue: InMemoryTaskQueue,
    snapshots_repo: InMemorySnapshotRepository,
) -> UseCases:
    workspaces = InMemoryWorkspaceRepository()
    documents = InMemoryDocumentRepository()
    snapshots = snapshots_repo
    ingestions = InMemoryIngestionRepository()
    ids = SequentialIds()
    access = AccessControl(memberships)
    engine = PycrdtEngine()
    realtime = RealtimeUseCases(
        documents, update_log, engine, access, snapshots, clock, ids
    )
    knowledge = KnowledgeUseCases(
        workspaces,
        ingestions,
        rag,
        access,
        clock,
        blobs=blobs,
        queue=task_queue,
    )
    connectors = ConnectorUseCases(
        connector_repo, mcp_client, secret_box, access, clock, ids
    )
    sharing = SharingUseCases(
        documents,
        memberships,
        InMemoryShareLinkRepository(),
        InMemoryCommentRepository(),
        access,
        clock,
        ids,
    )
    return UseCases(
        workspaces=WorkspaceUseCases(workspaces, memberships, clock, ids, rag),
        documents=DocumentUseCases(documents, access, clock, ids),
        snapshots=SnapshotUseCases(snapshots, documents, access, clock, ids),
        realtime=realtime,
        knowledge=knowledge,
        connectors=connectors,
        agent=AgentUseCases(
            llm,
            documents,
            realtime,
            knowledge,
            agent_runs,
            FileExtractor(),
            engine,
            access,
            clock,
            ids,
            model_name="scripted-test-model",
            connectors=connectors,
        ),
        sharing=sharing,
        api_keys=ApiKeyUseCases(InMemoryApiKeyRepository(), clock, ids),
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
