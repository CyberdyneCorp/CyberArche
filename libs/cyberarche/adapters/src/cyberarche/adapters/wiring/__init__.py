"""The composition root: the only place inbound and outbound adapters meet.

All three deployables (api, mcp, workers) build the same Container.
Backend selection is by configuration: "postgres" for real deployments,
"memory" for tests and the dockerless sample runtime.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

import httpx

from cyberarche.application.authz import AccessControl
from cyberarche.application.ports.identity import (
    AuthGatewayPort,
    AuthorizationPort,
    ServiceTokenPort,
    TokenPort,
)
from cyberarche.application.ports.repositories import (
    DocumentRepository,
    MembershipRepository,
    SnapshotRepository,
    WorkspaceRepository,
)
from cyberarche.application.ports.agent import AgentRunRepository
from cyberarche.application.ports.api_keys import ApiKeyRepository
from cyberarche.application.ports.bus import PeerBusPort
from cyberarche.application.ports.crdt import CrdtEnginePort, UpdateLogPort
from cyberarche.application.ports.code_exec import CodeExecutionPort
from cyberarche.application.ports.images import ImageGenerationPort
from cyberarche.application.ports.inferred_links import InferredLinkRepository
from cyberarche.application.ports.meetings import MeetingsPort
from cyberarche.application.ports.web_media import WebMediaPort
from cyberarche.application.ports.notifications import (
    NotificationChannelPort,
    NotificationPreferencesRepository,
    NotificationRepository,
)
from cyberarche.application.ports.agent_memory import (
    AgentMemoryRepository,
    CustomInstructionsRepository,
)
from cyberarche.application.ports.google_workspace import (
    GoogleConnectionRepository,
    GoogleWorkspacePort,
)
from cyberarche.application.ports.scheduled_agents import ScheduledAgentRepository
from cyberarche.application.ports.skills import AgentSkillRepository
from cyberarche.application.ports.templates import TemplateRepository
from cyberarche.application.ports.llm import LLMConfig, LLMPort
from cyberarche.application.ports.mcp import (
    ConnectorRepository,
    McpClientPort,
    SecretBoxPort,
)
from cyberarche.application.ports.queue import TaskQueuePort
from cyberarche.application.ports.rag import IngestionRepository, RagPort
from cyberarche.application.ports.sharing import CommentRepository, ShareLinkRepository
from cyberarche.application.ports.storage import BlobStoragePort
from cyberarche.application.ports.folders import FolderRepository
from cyberarche.application.ports.teamspaces import (
    FavoriteRepository,
    TeamspaceRepository,
)
from cyberarche.application.use_cases import UseCases
from cyberarche.application.use_cases.agent import AgentUseCases
from cyberarche.application.use_cases.api_keys import (
    ApiKeyUseCases,
    CompositeTokenVerifier,
)
from cyberarche.application.use_cases.connectors import ConnectorUseCases
from cyberarche.application.use_cases.documents import DocumentUseCases
from cyberarche.application.use_cases.files import FileUseCases
from cyberarche.application.use_cases.links import LinksUseCases
from cyberarche.application.use_cases.meeting_notes import MeetingNotesUseCases
from cyberarche.application.use_cases.folders import FolderUseCases
from cyberarche.application.use_cases.knowledge import KnowledgeUseCases
from cyberarche.application.use_cases.realtime import RealtimeUseCases
from cyberarche.application.use_cases.search import SearchUseCases
from cyberarche.application.use_cases.workspace_chat import WorkspaceChatUseCases
from cyberarche.application.use_cases.notifications import (
    NotificationDigestUseCases,
    NotificationDispatcher,
    NotificationPreferencesUseCases,
    NotificationUseCases,
)
from cyberarche.application.use_cases.sharing import SharingUseCases
from cyberarche.application.use_cases.agent_persona import AgentPersonaUseCases
from cyberarche.application.use_cases.google_workspace import GoogleWorkspaceUseCases
from cyberarche.application.use_cases.scheduled_agents import ScheduledAgentUseCases
from cyberarche.application.use_cases.skills import AgentSkillUseCases
from cyberarche.application.use_cases.templates import TemplateUseCases
from cyberarche.application.use_cases.teamspaces import (
    FavoriteUseCases,
    TeamspaceUseCases,
)
from cyberarche.application.use_cases.snapshots import SnapshotUseCases
from cyberarche.application.use_cases.workspaces import WorkspaceUseCases
from cyberarche.adapters.outbound.crdt.pycrdt_engine import PycrdtEngine
from cyberarche.adapters.outbound.extraction.files import FileExtractor
from cyberarche.adapters.outbound.auth.cyberdyne import (
    ClientCredentialsTokenSource,
    CyberdyneAuthConfig,
    CyberdyneAuthGateway,
    IamAuthorization,
    JwksTokenVerifier,
)


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class UuidIds:
    def new_id(self) -> str:
        return uuid.uuid4().hex


@dataclass(frozen=True, slots=True)
class WiringConfig:
    backend: Literal["postgres", "memory"] = "memory"
    database_url: str = ""
    auth_base_url: str = ""
    auth_client_id: str = ""
    auth_client_secret: str = ""
    auth_audience: str | None = None
    auth_issuer: str | None = None  # None => derive from auth_base_url (OIDC issuer)
    auth_tenant_claim: str = "org_id"
    rag_base_url: str = ""
    rag_api_token: str = ""
    rag_webhook_secret: str = ""
    llm_provider: str = "anthropic"  # "anthropic" | "openai" | "local"
    llm_model: str = "claude-sonnet-5"
    llm_api_key: str = ""
    llm_base_url: str = ""
    # Image generation (agent generate_image tool). Empty api_key = disabled.
    image_api_key: str = ""
    image_model: str = "gpt-image-1"
    image_base_url: str = ""  # OpenAI-compatible images endpoint; empty = OpenAI
    # Python code execution (agent run_python tool). Empty URL = disabled; needs
    # CyberdyneAuth service-token credentials to authenticate to the interpreter.
    interpreter_base_url: str = ""
    # Meeting transcripts (agent meeting tools). Empty URL = disabled; the agent
    # calls it with the caller's own access token (per-user data).
    meetings_base_url: str = ""
    # Web search + YouTube tools (agent web_media tools) via the DAO backend.
    # Empty URL = disabled; called with the caller's own forwarded access token.
    dao_base_url: str = ""
    # Google Workspace connector (Gmail/Calendar/Docs). Empty client id/secret =
    # disabled (the connector is not offered).
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = ""
    connector_secret_key: str = ""
    # Shared infrastructure for multi-replica deployments (12.5/12.6):
    # with redis_url set, live realtime fanout and the job queue go through
    # Redis; unset falls back to single-process in-memory implementations.
    redis_url: str = ""
    blob_dir: str = ""  # filesystem blob storage root; empty = in-memory
    # Outbound notification webhook (Slack-style incoming webhook / HTTP receiver).
    # Empty = no channel is built, so notifications stay in-app only (today's
    # behaviour). Set it to fan enabled notifications out to the URL.
    notification_webhook_url: str = ""
    # Per-user minimum interval between scheduled email digests (seconds).
    digest_interval_seconds: int = 86400


@dataclass(slots=True)
class Container:
    config: WiringConfig
    token_port: TokenPort
    service_tokens: ServiceTokenPort | None
    authorization: AuthorizationPort | None
    auth_gateway: AuthGatewayPort | None
    workspaces: WorkspaceRepository
    documents: DocumentRepository
    snapshots: SnapshotRepository
    memberships: MembershipRepository
    update_log: UpdateLogPort
    crdt_engine: CrdtEnginePort
    ingestions: IngestionRepository
    rag: RagPort
    llm: LLMPort
    agent_runs: AgentRunRepository
    connectors: ConnectorRepository
    mcp_client: McpClientPort
    secret_box: SecretBoxPort
    share_links: ShareLinkRepository
    comments: CommentRepository
    teamspaces: TeamspaceRepository
    favorites: FavoriteRepository
    folders: FolderRepository
    blobs: BlobStoragePort
    queue: TaskQueuePort
    peer_bus: PeerBusPort
    web_media: WebMediaPort | None
    use_cases: UseCases
    _closers: list = None  # awaited on shutdown, in order

    async def aclose(self) -> None:
        for closer in self._closers or []:
            await closer()


def _build_use_cases(
    workspaces: WorkspaceRepository,
    documents: DocumentRepository,
    snapshots: SnapshotRepository,
    memberships: MembershipRepository,
    update_log: UpdateLogPort,
    crdt_engine: CrdtEnginePort,
    ingestions: IngestionRepository,
    rag: RagPort,
    llm: LLMPort,
    images: ImageGenerationPort | None,
    code: CodeExecutionPort | None,
    meetings: MeetingsPort | None,
    web_media: WebMediaPort | None,
    agent_runs: AgentRunRepository,
    connectors: ConnectorRepository,
    mcp_client: McpClientPort,
    secret_box: SecretBoxPort,
    share_links: ShareLinkRepository,
    comments: CommentRepository,
    teamspaces: TeamspaceRepository,
    favorites: FavoriteRepository,
    folders: FolderRepository,
    blobs: BlobStoragePort,
    queue: TaskQueuePort,
    peer_bus: PeerBusPort,
    api_keys: ApiKeyRepository,
    inferred_links: InferredLinkRepository,
    notifications: NotificationRepository,
    notification_prefs: NotificationPreferencesRepository,
    dispatcher: NotificationDispatcher,
    notification_digest: NotificationDigestUseCases,
    templates: TemplateRepository,
    custom_instructions: CustomInstructionsRepository,
    agent_memories: AgentMemoryRepository,
    agent_skills: AgentSkillRepository,
    scheduled_agents: ScheduledAgentRepository,
    google_connections: GoogleConnectionRepository,
    google_port: GoogleWorkspacePort | None,
    model_name: str,
    clock,
    ids,
) -> UseCases:
    access = AccessControl(memberships, teamspaces)
    google = (
        GoogleWorkspaceUseCases(
            google_connections, google_port, secret_box, access, clock, ids
        )
        if google_port is not None
        else None
    )
    persona = AgentPersonaUseCases(
        custom_instructions, agent_memories, access, clock, ids
    )
    realtime = RealtimeUseCases(
        documents, update_log, crdt_engine, access, snapshots, clock, ids, peer_bus
    )
    knowledge = KnowledgeUseCases(
        workspaces, ingestions, rag, access, clock, blobs=blobs, queue=queue
    )
    connector_use_cases = ConnectorUseCases(
        connectors, mcp_client, secret_box, access, clock, ids
    )
    document_use_cases = DocumentUseCases(
        documents, access, clock, ids, teamspaces, folders
    )
    search = SearchUseCases(documents, realtime, crdt_engine, access)
    workspace_chat = WorkspaceChatUseCases(
        llm, rag, workspaces, search, access, persona=persona
    )
    agent_use_cases = AgentUseCases(
        llm,
        documents,
        realtime,
        knowledge,
        agent_runs,
        FileExtractor(),
        crdt_engine,
        access,
        clock,
        ids,
        model_name=model_name,
        connectors=connector_use_cases,
        images=images,
        blobs=blobs,
        code=code,
        meetings=meetings,
        web_media=web_media,
        persona=persona,
        google=google,
    )
    return UseCases(
        workspaces=WorkspaceUseCases(workspaces, memberships, clock, ids, rag),
        documents=document_use_cases,
        snapshots=SnapshotUseCases(
            snapshots, documents, access, clock, ids, crdt_engine, realtime
        ),
        realtime=realtime,
        knowledge=knowledge,
        connectors=connector_use_cases,
        agent=agent_use_cases,
        scheduled_agents=ScheduledAgentUseCases(
            scheduled_agents,
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
        google=google,
        persona=persona,
        sharing=SharingUseCases(
            documents,
            memberships,
            share_links,
            comments,
            access,
            clock,
            ids,
            notifications=dispatcher,
        ),
        api_keys=ApiKeyUseCases(api_keys, clock, ids),
        teamspaces=TeamspaceUseCases(teamspaces, documents, folders, access, clock, ids),
        favorites=FavoriteUseCases(favorites, documents, access),
        folders=FolderUseCases(folders, documents, access, clock, ids),
        files=FileUseCases(blobs, access, ids),
        links=LinksUseCases(
            documents,
            realtime,
            crdt_engine,
            access,
            llm=llm,
            inferred_links=inferred_links,
            clock=clock,
        ),
        search=search,
        workspace_chat=workspace_chat,
        notifications=NotificationUseCases(notifications),
        notification_prefs=NotificationPreferencesUseCases(notification_prefs),
        notification_digest=notification_digest,
        skills=AgentSkillUseCases(agent_skills, access, clock, ids),
        templates=TemplateUseCases(
            templates,
            document_use_cases,
            realtime,
            crdt_engine,
            access,
            clock,
            ids,
        ),
    )


def _build_llm(config: WiringConfig, http: httpx.AsyncClient) -> LLMPort:
    llm_config = LLMConfig(
        provider=config.llm_provider,
        model=config.llm_model,
        api_key=config.llm_api_key,
        base_url=config.llm_base_url,
    )
    if config.llm_provider == "anthropic":
        from cyberarche.adapters.outbound.llm.anthropic import AnthropicLLM

        return AnthropicLLM(llm_config, http)
    # "openai" and "local" both speak the OpenAI-compatible protocol.
    from cyberarche.adapters.outbound.llm.openai_compatible import OpenAICompatibleLLM

    return OpenAICompatibleLLM(llm_config, http)


def _build_image_generator(config: WiringConfig, http: httpx.AsyncClient):
    """OpenAI image generator, or None when no image API key is configured."""
    if not config.image_api_key:
        return None
    from cyberarche.adapters.outbound.imagegen.openai_images import (
        OpenAIImageGenerator,
    )

    return OpenAIImageGenerator(
        http,
        api_key=config.image_api_key,
        model=config.image_model,
        base_url=config.image_base_url,
    )


def _build_code_executor(config: WiringConfig, service_tokens, shared_http):
    """Cyberdyne Python Interpreter adapter, or None when unconfigured. Uses the
    CyberdyneAuth service token (client-credentials) as the interpreter bearer."""
    if not config.interpreter_base_url or service_tokens is None:
        return None
    from cyberarche.adapters.outbound.code_exec.cyberdyne_interpreter import (
        CyberdyneInterpreterAdapter,
    )

    return CyberdyneInterpreterAdapter(
        config.interpreter_base_url, shared_http(), service_tokens.service_token
    )


def _build_meetings(config: WiringConfig, shared_http):
    """Cyberflies meetings adapter, or None when unconfigured. Authenticates per
    request with the caller's own access token (per-user data), not a service
    token, so it needs no credentials at construction."""
    if not config.meetings_base_url:
        return None
    from cyberarche.adapters.outbound.meetings.cyberflies import (
        CyberfliesMeetingsAdapter,
    )

    return CyberfliesMeetingsAdapter(config.meetings_base_url, shared_http())


def _build_web_media(config: WiringConfig, shared_http):
    """DAO-backend web search + YouTube adapter, or None when unconfigured.
    Authenticates per request with the caller's own forwarded access token (no
    service token), so it needs no credentials at construction."""
    if not config.dao_base_url:
        return None
    from cyberarche.adapters.outbound.web_media.dao_backend import (
        DaoBackendWebMediaAdapter,
    )

    return DaoBackendWebMediaAdapter(config.dao_base_url, shared_http())


def _build_google_port(config: WiringConfig, shared_http):
    """Google Workspace adapter, or None when OAuth credentials are unconfigured
    (the connector is simply not offered)."""
    if not config.google_client_id or not config.google_client_secret:
        return None
    from cyberarche.adapters.outbound.google.client import GoogleWorkspaceClient

    return GoogleWorkspaceClient(
        client_id=config.google_client_id,
        client_secret=config.google_client_secret,
        redirect_uri=config.google_redirect_uri,
        http=shared_http(),
    )


def _build_notification_channels(
    config: WiringConfig, shared_http
) -> tuple[NotificationChannelPort, ...]:
    """The configured outbound notification channels. Empty when nothing is
    configured, so notifications stay in-app only (today's behaviour)."""
    if not config.notification_webhook_url:
        return ()
    from cyberarche.adapters.outbound.notifications.webhook import (
        WebhookNotificationChannel,
    )

    return (WebhookNotificationChannel(config.notification_webhook_url, shared_http()),)


@dataclass(slots=True)
class _Repositories:
    workspaces: WorkspaceRepository
    documents: DocumentRepository
    snapshots: SnapshotRepository
    memberships: MembershipRepository
    update_log: UpdateLogPort
    ingestions: IngestionRepository
    agent_runs: AgentRunRepository
    connectors: ConnectorRepository
    share_links: ShareLinkRepository
    comments: CommentRepository
    api_keys: ApiKeyRepository
    teamspaces: TeamspaceRepository
    favorites: FavoriteRepository
    folders: FolderRepository
    inferred_links: InferredLinkRepository
    notifications: NotificationRepository
    notification_prefs: NotificationPreferencesRepository
    templates: TemplateRepository
    custom_instructions: CustomInstructionsRepository
    agent_memories: AgentMemoryRepository
    agent_skills: AgentSkillRepository
    scheduled_agents: ScheduledAgentRepository
    google_connections: GoogleConnectionRepository


async def _postgres_repositories(config: WiringConfig, closers: list) -> _Repositories:
    import asyncpg

    from cyberarche.adapters.outbound.postgres.api_keys import (
        PostgresApiKeyRepository,
    )
    from cyberarche.adapters.outbound.postgres.agent_runs import (
        PostgresAgentRunRepository,
    )
    from cyberarche.adapters.outbound.postgres.connectors import (
        PostgresConnectorRepository,
    )
    from cyberarche.adapters.outbound.postgres.ingestions import (
        PostgresIngestionRepository,
    )
    from cyberarche.adapters.outbound.postgres.repositories import (
        PostgresDocumentRepository,
        PostgresMembershipRepository,
        PostgresSnapshotRepository,
        PostgresWorkspaceRepository,
    )
    from cyberarche.adapters.outbound.postgres.sharing import (
        PostgresCommentRepository,
        PostgresShareLinkRepository,
    )
    from cyberarche.adapters.outbound.postgres.folders import PostgresFolderRepository
    from cyberarche.adapters.outbound.postgres.teamspaces import (
        PostgresFavoriteRepository,
        PostgresTeamspaceRepository,
    )
    from cyberarche.adapters.outbound.postgres.inferred_links import (
        PostgresInferredLinkRepository,
    )
    from cyberarche.adapters.outbound.postgres.notifications import (
        PostgresNotificationRepository,
    )
    from cyberarche.adapters.outbound.postgres.notification_prefs import (
        PostgresNotificationPreferencesRepository,
    )
    from cyberarche.adapters.outbound.postgres.templates import (
        PostgresTemplateRepository,
    )
    from cyberarche.adapters.outbound.postgres.agent_memory import (
        PostgresAgentMemoryRepository,
        PostgresCustomInstructionsRepository,
    )
    from cyberarche.adapters.outbound.postgres.skills import (
        PostgresAgentSkillRepository,
    )
    from cyberarche.adapters.outbound.postgres.scheduled_agents import (
        PostgresScheduledAgentRepository,
    )
    from cyberarche.adapters.outbound.postgres.google_connections import (
        PostgresGoogleConnectionRepository,
    )
    from cyberarche.adapters.outbound.postgres.update_log import PostgresUpdateLog

    pool = await asyncpg.create_pool(config.database_url)
    closers.append(pool.close)
    return _Repositories(
        workspaces=PostgresWorkspaceRepository(pool),
        documents=PostgresDocumentRepository(pool),
        snapshots=PostgresSnapshotRepository(pool),
        memberships=PostgresMembershipRepository(pool),
        update_log=PostgresUpdateLog(pool),
        ingestions=PostgresIngestionRepository(pool),
        agent_runs=PostgresAgentRunRepository(pool),
        connectors=PostgresConnectorRepository(pool),
        share_links=PostgresShareLinkRepository(pool),
        comments=PostgresCommentRepository(pool),
        api_keys=PostgresApiKeyRepository(pool),
        teamspaces=PostgresTeamspaceRepository(pool),
        favorites=PostgresFavoriteRepository(pool),
        folders=PostgresFolderRepository(pool),
        inferred_links=PostgresInferredLinkRepository(pool),
        notifications=PostgresNotificationRepository(pool),
        notification_prefs=PostgresNotificationPreferencesRepository(pool),
        templates=PostgresTemplateRepository(pool),
        custom_instructions=PostgresCustomInstructionsRepository(pool),
        agent_memories=PostgresAgentMemoryRepository(pool),
        agent_skills=PostgresAgentSkillRepository(pool),
        scheduled_agents=PostgresScheduledAgentRepository(pool),
        google_connections=PostgresGoogleConnectionRepository(pool),
    )


def _memory_repositories() -> _Repositories:
    from cyberarche.application.testing import fakes

    return _Repositories(
        workspaces=fakes.InMemoryWorkspaceRepository(),
        documents=fakes.InMemoryDocumentRepository(),
        snapshots=fakes.InMemorySnapshotRepository(),
        memberships=fakes.InMemoryMembershipRepository(),
        update_log=fakes.InMemoryUpdateLog(),
        ingestions=fakes.InMemoryIngestionRepository(),
        agent_runs=fakes.InMemoryAgentRunRepository(),
        connectors=fakes.InMemoryConnectorRepository(),
        share_links=fakes.InMemoryShareLinkRepository(),
        comments=fakes.InMemoryCommentRepository(),
        api_keys=fakes.InMemoryApiKeyRepository(),
        teamspaces=fakes.InMemoryTeamspaceRepository(),
        favorites=fakes.InMemoryFavoriteRepository(),
        folders=fakes.InMemoryFolderRepository(),
        inferred_links=fakes.InMemoryInferredLinkRepository(),
        notifications=fakes.InMemoryNotificationRepository(),
        notification_prefs=fakes.InMemoryNotificationPreferencesRepository(),
        templates=fakes.InMemoryTemplateRepository(),
        custom_instructions=fakes.InMemoryCustomInstructionsRepository(),
        agent_memories=fakes.InMemoryAgentMemoryRepository(),
        agent_skills=fakes.InMemoryAgentSkillRepository(),
        scheduled_agents=fakes.InMemoryScheduledAgentRepository(),
        google_connections=fakes.InMemoryGoogleConnectionRepository(),
    )


def _build_shared_infra(
    config: WiringConfig, closers: list
) -> tuple[BlobStoragePort, TaskQueuePort, PeerBusPort]:
    """Blob storage, task queue, and peer bus — Redis/filesystem when
    configured, in-memory single-process fallbacks otherwise."""
    from cyberarche.application.testing.fakes import (
        InMemoryBlobStorage,
        InMemoryTaskQueue,
        InProcessPeerBus,
    )

    if config.blob_dir:
        from cyberarche.adapters.outbound.objectstore.filesystem import (
            FilesystemBlobStorage,
        )

        blobs: BlobStoragePort = FilesystemBlobStorage(config.blob_dir)
    else:
        blobs = InMemoryBlobStorage()

    if config.redis_url:
        import redis.asyncio as aioredis

        from cyberarche.adapters.outbound.redis_infra.bus import RedisPeerBus
        from cyberarche.adapters.outbound.redis_infra.queue import RedisTaskQueue

        client = aioredis.from_url(config.redis_url)
        closers.append(client.aclose)
        queue: TaskQueuePort = RedisTaskQueue(client)
        peer_bus: PeerBusPort = RedisPeerBus(client)
    else:
        queue = InMemoryTaskQueue()
        peer_bus = InProcessPeerBus()
    return blobs, queue, peer_bus


def _build_secret_box(config: WiringConfig) -> SecretBoxPort:
    if config.connector_secret_key:
        from cyberarche.adapters.outbound.crypto import FernetSecretBox

        return FernetSecretBox(config.connector_secret_key)
    # Fail closed: the real (postgres) deployment MUST have a real key, or
    # connector credentials and Google OAuth tokens would be stored with the
    # non-encrypting NaiveSecretBox (security audit F-001).
    if config.backend == "postgres":
        raise ValueError(
            "connector_secret_key is required for the postgres backend "
            "(refusing to store secrets without real encryption)"
        )
    from cyberarche.application.testing.fakes import NaiveSecretBox

    return NaiveSecretBox()  # tests/sample runtime only


def _auth_config(config: WiringConfig) -> CyberdyneAuthConfig:
    return CyberdyneAuthConfig(
        base_url=config.auth_base_url,
        client_id=config.auth_client_id,
        client_secret=config.auth_client_secret,
        audience=config.auth_audience,
        # Default the expected issuer to the auth service's own base URL (its
        # OIDC issuer). CyberdyneAuth issues iss = the discovery issuer = base
        # URL; hard-coding a name would drift when it changes (see #47).
        issuer=config.auth_issuer or config.auth_base_url.rstrip("/") or None,
        tenant_claim=config.auth_tenant_claim,
    )


def _build_auth_stack(config: WiringConfig, shared_http):
    """(token_port, service_tokens, authorization) from CyberdyneAuth config."""
    if not config.auth_base_url:
        raise ValueError("auth_base_url is required unless a token_port is injected")
    auth_config = _auth_config(config)
    credentials = ClientCredentialsTokenSource(auth_config, shared_http())
    token_port = JwksTokenVerifier(auth_config, shared_http(), credentials)
    authorization = IamAuthorization(auth_config, shared_http(), credentials)
    return token_port, credentials, authorization


def _build_rag(config: WiringConfig, service_tokens, shared_http) -> RagPort:
    if not config.rag_base_url:
        from cyberarche.application.testing.fakes import InMemoryRag

        return InMemoryRag()
    from cyberarche.adapters.outbound.rag.cyberdyne_rag import CyberdyneRagAdapter

    if config.rag_api_token:
        async def rag_token() -> str:
            return config.rag_api_token
    elif service_tokens is not None:
        rag_token = service_tokens.service_token
    else:
        raise ValueError("RAG needs rag_api_token or CyberdyneAuth credentials")
    return CyberdyneRagAdapter(config.rag_base_url, shared_http(), rag_token)


def _build_llm_or_default(config: WiringConfig, shared_http) -> LLMPort:
    """Configured LLM adapter, or a scripted no-op LLM when no provider is
    configured (tests/sample runtime)."""
    if config.llm_api_key or config.llm_base_url:
        return _build_llm(config, shared_http())
    from cyberarche.application.testing.fakes import ScriptedLLM

    return ScriptedLLM([])  # no provider configured (tests/sample)


@dataclass(slots=True)
class _OptionalAdapters:
    images: ImageGenerationPort | None
    code: CodeExecutionPort | None
    meetings: MeetingsPort | None
    web_media: WebMediaPort | None
    google_port: GoogleWorkspacePort | None


def _build_optional_adapters(
    config: WiringConfig,
    service_tokens: ServiceTokenPort | None,
    shared_http,
    *,
    images: ImageGenerationPort | None,
    code: CodeExecutionPort | None,
    meetings: MeetingsPort | None,
    web_media: WebMediaPort | None,
    google_port: GoogleWorkspacePort | None,
) -> _OptionalAdapters:
    """Resolve the optional agent tool adapters: honor any injected override,
    otherwise build from config (each builder returns None when unconfigured)."""
    return _OptionalAdapters(
        images=images
        if images is not None
        else _build_image_generator(config, shared_http()),
        code=code
        if code is not None
        else _build_code_executor(config, service_tokens, shared_http),
        meetings=meetings
        if meetings is not None
        else _build_meetings(config, shared_http),
        web_media=web_media
        if web_media is not None
        else _build_web_media(config, shared_http),
        google_port=google_port
        if google_port is not None
        else _build_google_port(config, shared_http),
    )


async def build_container(
    config: WiringConfig,
    *,
    token_port: TokenPort | None = None,
    rag: RagPort | None = None,
    llm: LLMPort | None = None,
    images: ImageGenerationPort | None = None,
    code: CodeExecutionPort | None = None,
    meetings: MeetingsPort | None = None,
    web_media: WebMediaPort | None = None,
    google_port: GoogleWorkspacePort | None = None,
    mcp_client: McpClientPort | None = None,
    peer_bus: PeerBusPort | None = None,
    queue: TaskQueuePort | None = None,
) -> Container:
    """Build the container. `token_port`, `rag`, `llm`, `mcp_client`,
    `peer_bus`, and `queue` are injectable for tests and the dockerless
    sample runtime."""
    clock = SystemClock()
    ids = UuidIds()
    closers = []

    if config.backend == "postgres":
        repos = await _postgres_repositories(config, closers)
    else:
        repos = _memory_repositories()

    http: httpx.AsyncClient | None = None

    def shared_http() -> httpx.AsyncClient:
        nonlocal http
        if http is None:
            http = httpx.AsyncClient(timeout=30.0)
            closers.append(http.aclose)
        return http

    service_tokens: ServiceTokenPort | None = None
    authorization: AuthorizationPort | None = None
    if token_port is None:
        token_port, service_tokens, authorization = _build_auth_stack(
            config, shared_http
        )
    auth_gateway: AuthGatewayPort | None = None
    if config.auth_base_url:
        auth_gateway = CyberdyneAuthGateway(_auth_config(config), shared_http())

    # API keys ride the same TokenPort seam (design D-1): cak_ secrets
    # resolve locally, everything else delegates to the verifier above.
    token_port = CompositeTokenVerifier(repos.api_keys, token_port, clock)

    if rag is None:
        rag = _build_rag(config, service_tokens, shared_http)

    if llm is None:
        llm = _build_llm_or_default(config, shared_http)

    adapters = _build_optional_adapters(
        config,
        service_tokens,
        shared_http,
        images=images,
        code=code,
        meetings=meetings,
        web_media=web_media,
        google_port=google_port,
    )
    images = adapters.images
    code = adapters.code
    meetings = adapters.meetings
    web_media = adapters.web_media
    google_port = adapters.google_port

    if mcp_client is None:
        from cyberarche.adapters.outbound.mcp_client.fastmcp_client import (
            FastMcpClientAdapter,
        )

        # Private/loopback connector endpoints are allowed only outside the
        # real deployment (memory backend = local/dev/tests). In postgres the
        # SSRF guard blocks internal targets (security audit F-002).
        mcp_client = FastMcpClientAdapter(
            allow_private_networks=config.backend != "postgres"
        )

    secret_box = _build_secret_box(config)
    blobs, built_queue, built_bus = _build_shared_infra(config, closers)
    queue = queue or built_queue
    peer_bus = peer_bus or built_bus
    (
        workspaces,
        documents,
        snapshots,
        memberships,
        update_log,
        ingestions,
        agent_runs,
        connectors,
        share_links,
        comments,
    ) = (
        repos.workspaces,
        repos.documents,
        repos.snapshots,
        repos.memberships,
        repos.update_log,
        repos.ingestions,
        repos.agent_runs,
        repos.connectors,
        repos.share_links,
        repos.comments,
    )
    crdt_engine = PycrdtEngine()
    channels = _build_notification_channels(config, shared_http)
    dispatcher = NotificationDispatcher(
        repos.notifications, repos.notification_prefs, channels
    )
    notification_digest = NotificationDigestUseCases(
        repos.notifications,
        repos.notification_prefs,
        channels,
        min_interval_seconds=config.digest_interval_seconds,
    )
    return Container(
        config=config,
        token_port=token_port,
        service_tokens=service_tokens,
        authorization=authorization,
        auth_gateway=auth_gateway,
        workspaces=workspaces,
        documents=documents,
        snapshots=snapshots,
        memberships=memberships,
        update_log=update_log,
        crdt_engine=crdt_engine,
        ingestions=ingestions,
        rag=rag,
        llm=llm,
        agent_runs=agent_runs,
        connectors=connectors,
        mcp_client=mcp_client,
        secret_box=secret_box,
        share_links=share_links,
        comments=comments,
        teamspaces=repos.teamspaces,
        favorites=repos.favorites,
        folders=repos.folders,
        blobs=blobs,
        queue=queue,
        peer_bus=peer_bus,
        web_media=web_media,
        use_cases=_build_use_cases(
            workspaces,
            documents,
            snapshots,
            memberships,
            update_log,
            crdt_engine,
            ingestions,
            rag,
            llm,
            images,
            code,
            meetings,
            web_media,
            agent_runs,
            connectors,
            mcp_client,
            secret_box,
            share_links,
            comments,
            repos.teamspaces,
            repos.favorites,
            repos.folders,
            blobs,
            queue,
            peer_bus,
            repos.api_keys,
            repos.inferred_links,
            repos.notifications,
            repos.notification_prefs,
            dispatcher,
            notification_digest,
            repos.templates,
            repos.custom_instructions,
            repos.agent_memories,
            repos.agent_skills,
            repos.scheduled_agents,
            repos.google_connections,
            google_port,
            config.llm_model,
            clock,
            ids,
        ),
        _closers=closers,
    )
