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
    FakeGoogleWorkspace,
    InMemoryAgentMemoryRepository,
    InMemoryAgentRunRepository,
    InMemoryAgentSkillRepository,
    InMemoryGoogleConnectionRepository,
    InMemoryScheduledAgentRepository,
    InMemoryApiKeyRepository,
    InMemoryCustomInstructionsRepository,
    InMemoryBlobStorage,
    InMemoryCollectionRepository,
    InMemoryCommentRepository,
    InMemoryConnectorRepository,
    InMemoryDocumentRepository,
    InMemoryFavoriteRepository,
    InMemoryFolderRepository,
    InMemoryIngestionRepository,
    InMemoryMembershipRepository,
    InMemoryRag,
    InMemoryShareLinkRepository,
    InMemorySnapshotRepository,
    InMemoryTeamspaceRepository,
    InMemoryTaskQueue,
    InMemoryUpdateLog,
    InMemoryWorkspaceRepository,
    NaiveSecretBox,
    ScriptedCodeExecutor,
    ScriptedImageGenerator,
    ScriptedLLM,
    InMemoryInferredLinkRepository,
    InMemoryNotificationRepository,
    InMemoryNotificationPreferencesRepository,
    InMemoryPushSubscriptionRepository,
    InMemoryTemplateRepository,
    ScriptedMeetings,
    ScriptedWebMedia,
    SequentialIds,
    StaticTokenPort,
)
from cyberarche.application.use_cases import UseCases
from cyberarche.application.use_cases.agent import AgentUseCases
from cyberarche.application.use_cases.agent_persona import AgentPersonaUseCases
from cyberarche.application.use_cases.google_workspace import GoogleWorkspaceUseCases
from cyberarche.application.use_cases.scheduled_agents import ScheduledAgentUseCases
from cyberarche.application.use_cases.skills import AgentSkillUseCases
from cyberarche.application.use_cases.api_keys import ApiKeyUseCases
from cyberarche.application.use_cases.collections import CollectionUseCases
from cyberarche.application.use_cases.connectors import ConnectorUseCases
from cyberarche.application.use_cases.documents import DocumentUseCases
from cyberarche.application.use_cases.files import FileUseCases
from cyberarche.application.use_cases.folders import FolderUseCases
from cyberarche.application.use_cases.links import LinksUseCases
from cyberarche.application.use_cases.meeting_notes import MeetingNotesUseCases
from cyberarche.application.use_cases.notifications import (
    NotificationDigestUseCases,
    NotificationDispatcher,
    NotificationPreferencesUseCases,
    NotificationUseCases,
    PushSubscriptionUseCases,
)
from cyberarche.application.use_cases.search import SearchUseCases
from cyberarche.application.use_cases.workspace_chat import WorkspaceChatUseCases
from cyberarche.application.use_cases.templates import TemplateUseCases
from cyberarche.application.use_cases.knowledge import KnowledgeUseCases
from cyberarche.application.use_cases.realtime import RealtimeUseCases
from cyberarche.application.use_cases.sharing import SharingUseCases
from cyberarche.application.use_cases.teamspaces import (
    FavoriteUseCases,
    TeamspaceUseCases,
)
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
def images() -> ScriptedImageGenerator:
    return ScriptedImageGenerator()


@pytest.fixture
def code_exec() -> ScriptedCodeExecutor:
    return ScriptedCodeExecutor()


@pytest.fixture
def meetings() -> ScriptedMeetings:
    return ScriptedMeetings()


@pytest.fixture
def web_media() -> ScriptedWebMedia:
    return ScriptedWebMedia()


@pytest.fixture
def scheduled_repo() -> InMemoryScheduledAgentRepository:
    return InMemoryScheduledAgentRepository()


@pytest.fixture
def google_repo() -> InMemoryGoogleConnectionRepository:
    return InMemoryGoogleConnectionRepository()


@pytest.fixture
def google_port() -> FakeGoogleWorkspace:
    return FakeGoogleWorkspace()


@pytest.fixture
def inferred_links() -> InMemoryInferredLinkRepository:
    return InMemoryInferredLinkRepository()


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
def teamspace_repo() -> InMemoryTeamspaceRepository:
    return InMemoryTeamspaceRepository()


@pytest.fixture
def favorite_repo() -> InMemoryFavoriteRepository:
    return InMemoryFavoriteRepository()


@pytest.fixture
def use_cases(
    clock: FixedClock,
    update_log: InMemoryUpdateLog,
    memberships: InMemoryMembershipRepository,
    rag: InMemoryRag,
    llm: ScriptedLLM,
    images: ScriptedImageGenerator,
    code_exec: ScriptedCodeExecutor,
    meetings: ScriptedMeetings,
    web_media: ScriptedWebMedia,
    scheduled_repo: InMemoryScheduledAgentRepository,
    google_repo: InMemoryGoogleConnectionRepository,
    google_port: FakeGoogleWorkspace,
    inferred_links: InMemoryInferredLinkRepository,
    agent_runs: InMemoryAgentRunRepository,
    mcp_client: FakeMcpClient,
    secret_box: NaiveSecretBox,
    connector_repo: InMemoryConnectorRepository,
    blobs: InMemoryBlobStorage,
    task_queue: InMemoryTaskQueue,
    snapshots_repo: InMemorySnapshotRepository,
    teamspace_repo: InMemoryTeamspaceRepository,
    favorite_repo: InMemoryFavoriteRepository,
) -> UseCases:
    workspaces = InMemoryWorkspaceRepository()
    documents = InMemoryDocumentRepository()
    snapshots = snapshots_repo
    ingestions = InMemoryIngestionRepository()
    ids = SequentialIds()
    access = AccessControl(memberships, teamspace_repo)
    folder_repo = InMemoryFolderRepository()
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
    notification_repo = InMemoryNotificationRepository()
    notification_prefs_repo = InMemoryNotificationPreferencesRepository()
    push_subscriptions_repo = InMemoryPushSubscriptionRepository()
    dispatcher = NotificationDispatcher(notification_repo, notification_prefs_repo)
    sharing = SharingUseCases(
        documents,
        memberships,
        InMemoryShareLinkRepository(),
        InMemoryCommentRepository(),
        access,
        clock,
        ids,
        notifications=dispatcher,
    )
    document_use_cases = DocumentUseCases(
        documents, access, clock, ids, teamspace_repo, folder_repo
    )
    persona = AgentPersonaUseCases(
        InMemoryCustomInstructionsRepository(),
        InMemoryAgentMemoryRepository(),
        access,
        clock,
        ids,
    )
    search = SearchUseCases(documents, realtime, engine, access)
    workspace_chat = WorkspaceChatUseCases(
        llm, rag, workspaces, search, access, persona=persona
    )
    google = GoogleWorkspaceUseCases(
        google_repo, google_port, secret_box, access, clock, ids
    )
    agent_use_cases = AgentUseCases(
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
        images=images,
        blobs=blobs,
        code=code_exec,
        meetings=meetings,
        web_media=web_media,
        persona=persona,
        google=google,
    )
    return UseCases(
        workspaces=WorkspaceUseCases(workspaces, memberships, clock, ids, rag),
        documents=document_use_cases,
        snapshots=SnapshotUseCases(
            snapshots, documents, access, clock, ids, engine, realtime
        ),
        realtime=realtime,
        knowledge=knowledge,
        connectors=connectors,
        agent=agent_use_cases,
        scheduled_agents=ScheduledAgentUseCases(
            scheduled_repo,
            agent_use_cases,
            document_use_cases,
            dispatcher,
            access,
            clock,
            ids,
        ),
        meeting_notes=MeetingNotesUseCases(
            meetings, llm, document_use_cases, agent_use_cases, ids
        ),
        persona=persona,
        google=google,
        skills=AgentSkillUseCases(InMemoryAgentSkillRepository(), access, clock, ids),
        sharing=sharing,
        api_keys=ApiKeyUseCases(InMemoryApiKeyRepository(), clock, ids),
        teamspaces=TeamspaceUseCases(
            teamspace_repo, documents, folder_repo, access, clock, ids
        ),
        favorites=FavoriteUseCases(favorite_repo, documents, access),
        collections=CollectionUseCases(
            InMemoryCollectionRepository(),
            documents,
            document_use_cases,
            access,
            clock,
            ids,
        ),
        folders=FolderUseCases(folder_repo, documents, access, clock, ids),
        files=FileUseCases(blobs, access, ids),
        links=LinksUseCases(
            documents,
            realtime,
            engine,
            access,
            llm=llm,
            inferred_links=inferred_links,
            clock=clock,
        ),
        search=search,
        workspace_chat=workspace_chat,
        notifications=NotificationUseCases(notification_repo),
        notification_prefs=NotificationPreferencesUseCases(notification_prefs_repo),
        push_subscriptions=PushSubscriptionUseCases(push_subscriptions_repo, clock),
        notification_digest=NotificationDigestUseCases(
            notification_repo,
            notification_prefs_repo,
            min_interval_seconds=86400,
        ),
        templates=TemplateUseCases(
            InMemoryTemplateRepository(),
            document_use_cases,
            realtime,
            engine,
            access,
            clock,
            ids,
        ),
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
