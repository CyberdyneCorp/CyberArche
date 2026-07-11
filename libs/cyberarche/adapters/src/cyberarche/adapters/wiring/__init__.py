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
from cyberarche.application.ports.meetings import MeetingsPort
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
from cyberarche.application.use_cases.folders import FolderUseCases
from cyberarche.application.use_cases.knowledge import KnowledgeUseCases
from cyberarche.application.use_cases.realtime import RealtimeUseCases
from cyberarche.application.use_cases.sharing import SharingUseCases
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
    connector_secret_key: str = ""
    # Shared infrastructure for multi-replica deployments (12.5/12.6):
    # with redis_url set, live realtime fanout and the job queue go through
    # Redis; unset falls back to single-process in-memory implementations.
    redis_url: str = ""
    blob_dir: str = ""  # filesystem blob storage root; empty = in-memory


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
    model_name: str,
    clock,
    ids,
) -> UseCases:
    access = AccessControl(memberships, teamspaces)
    realtime = RealtimeUseCases(
        documents, update_log, crdt_engine, access, snapshots, clock, ids, peer_bus
    )
    knowledge = KnowledgeUseCases(
        workspaces, ingestions, rag, access, clock, blobs=blobs, queue=queue
    )
    connector_use_cases = ConnectorUseCases(
        connectors, mcp_client, secret_box, access, clock, ids
    )
    return UseCases(
        workspaces=WorkspaceUseCases(workspaces, memberships, clock, ids, rag),
        documents=DocumentUseCases(documents, access, clock, ids, teamspaces, folders),
        snapshots=SnapshotUseCases(
            snapshots, documents, access, clock, ids, crdt_engine, realtime
        ),
        realtime=realtime,
        knowledge=knowledge,
        connectors=connector_use_cases,
        agent=AgentUseCases(
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
        ),
        sharing=SharingUseCases(
            documents, memberships, share_links, comments, access, clock, ids
        ),
        api_keys=ApiKeyUseCases(api_keys, clock, ids),
        teamspaces=TeamspaceUseCases(teamspaces, documents, folders, access, clock, ids),
        favorites=FavoriteUseCases(favorites, documents, access),
        folders=FolderUseCases(folders, documents, access, clock, ids),
        files=FileUseCases(blobs, access, ids),
        links=LinksUseCases(documents, realtime, crdt_engine, access),
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
    from cyberarche.application.testing.fakes import NaiveSecretBox

    return NaiveSecretBox()  # tests/sample runtime only


def _auth_config(config: WiringConfig) -> CyberdyneAuthConfig:
    return CyberdyneAuthConfig(
        base_url=config.auth_base_url,
        client_id=config.auth_client_id,
        client_secret=config.auth_client_secret,
        audience=config.auth_audience,
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


async def build_container(
    config: WiringConfig,
    *,
    token_port: TokenPort | None = None,
    rag: RagPort | None = None,
    llm: LLMPort | None = None,
    images: ImageGenerationPort | None = None,
    code: CodeExecutionPort | None = None,
    meetings: MeetingsPort | None = None,
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
        if config.llm_api_key or config.llm_base_url:
            llm = _build_llm(config, shared_http())
        else:
            from cyberarche.application.testing.fakes import ScriptedLLM

            llm = ScriptedLLM([])  # no provider configured (tests/sample)

    if images is None:
        images = _build_image_generator(config, shared_http())

    if code is None:
        code = _build_code_executor(config, service_tokens, shared_http)

    if meetings is None:
        meetings = _build_meetings(config, shared_http)

    if mcp_client is None:
        from cyberarche.adapters.outbound.mcp_client.fastmcp_client import (
            FastMcpClientAdapter,
        )

        mcp_client = FastMcpClientAdapter()

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
            config.llm_model,
            clock,
            ids,
        ),
        _closers=closers,
    )
