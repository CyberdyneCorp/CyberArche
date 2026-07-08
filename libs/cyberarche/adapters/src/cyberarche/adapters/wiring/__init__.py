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
from cyberarche.application.ports.crdt import CrdtEnginePort, UpdateLogPort
from cyberarche.application.ports.rag import IngestionRepository, RagPort
from cyberarche.application.use_cases import UseCases
from cyberarche.application.use_cases.documents import DocumentUseCases
from cyberarche.application.use_cases.knowledge import KnowledgeUseCases
from cyberarche.application.use_cases.realtime import RealtimeUseCases
from cyberarche.application.use_cases.snapshots import SnapshotUseCases
from cyberarche.application.use_cases.workspaces import WorkspaceUseCases
from cyberarche.adapters.outbound.crdt.pycrdt_engine import PycrdtEngine
from cyberarche.adapters.outbound.auth.cyberdyne import (
    ClientCredentialsTokenSource,
    CyberdyneAuthConfig,
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


@dataclass(slots=True)
class Container:
    config: WiringConfig
    token_port: TokenPort
    service_tokens: ServiceTokenPort | None
    authorization: AuthorizationPort | None
    workspaces: WorkspaceRepository
    documents: DocumentRepository
    snapshots: SnapshotRepository
    memberships: MembershipRepository
    update_log: UpdateLogPort
    crdt_engine: CrdtEnginePort
    ingestions: IngestionRepository
    rag: RagPort
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
    clock,
    ids,
) -> UseCases:
    access = AccessControl(memberships)
    return UseCases(
        workspaces=WorkspaceUseCases(workspaces, memberships, clock, ids, rag),
        documents=DocumentUseCases(documents, access, clock, ids),
        snapshots=SnapshotUseCases(snapshots, documents, access, clock, ids),
        realtime=RealtimeUseCases(documents, update_log, crdt_engine, access),
        knowledge=KnowledgeUseCases(workspaces, ingestions, rag, access, clock),
    )


async def build_container(
    config: WiringConfig,
    *,
    token_port: TokenPort | None = None,
    rag: RagPort | None = None,
) -> Container:
    """Build the container. `token_port` and `rag` are injectable for tests
    and the dockerless sample runtime."""
    clock = SystemClock()
    ids = UuidIds()
    closers = []

    if config.backend == "postgres":
        import asyncpg

        from cyberarche.adapters.outbound.postgres.repositories import (
            PostgresDocumentRepository,
            PostgresMembershipRepository,
            PostgresSnapshotRepository,
            PostgresWorkspaceRepository,
        )
        from cyberarche.adapters.outbound.postgres.ingestions import (
            PostgresIngestionRepository,
        )
        from cyberarche.adapters.outbound.postgres.update_log import PostgresUpdateLog

        pool = await asyncpg.create_pool(config.database_url)
        closers.append(pool.close)
        workspaces = PostgresWorkspaceRepository(pool)
        documents = PostgresDocumentRepository(pool)
        snapshots = PostgresSnapshotRepository(pool)
        memberships = PostgresMembershipRepository(pool)
        update_log = PostgresUpdateLog(pool)
        ingestions = PostgresIngestionRepository(pool)
    else:
        from cyberarche.application.testing.fakes import (
            InMemoryDocumentRepository,
            InMemoryIngestionRepository,
            InMemoryMembershipRepository,
            InMemorySnapshotRepository,
            InMemoryUpdateLog,
            InMemoryWorkspaceRepository,
        )

        workspaces = InMemoryWorkspaceRepository()
        documents = InMemoryDocumentRepository()
        snapshots = InMemorySnapshotRepository()
        memberships = InMemoryMembershipRepository()
        update_log = InMemoryUpdateLog()
        ingestions = InMemoryIngestionRepository()

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
        if not config.auth_base_url:
            raise ValueError(
                "auth_base_url is required unless a token_port is injected"
            )
        auth_config = CyberdyneAuthConfig(
            base_url=config.auth_base_url,
            client_id=config.auth_client_id,
            client_secret=config.auth_client_secret,
            audience=config.auth_audience,
            tenant_claim=config.auth_tenant_claim,
        )
        credentials = ClientCredentialsTokenSource(auth_config, shared_http())
        token_port = JwksTokenVerifier(auth_config, shared_http(), credentials)
        service_tokens = credentials
        authorization = IamAuthorization(auth_config, shared_http(), credentials)

    if rag is None:
        if config.rag_base_url:
            from cyberarche.adapters.outbound.rag.cyberdyne_rag import (
                CyberdyneRagAdapter,
            )

            if config.rag_api_token:
                async def rag_token() -> str:
                    return config.rag_api_token
            elif service_tokens is not None:
                rag_token = service_tokens.service_token
            else:
                raise ValueError("RAG needs rag_api_token or CyberdyneAuth credentials")
            rag = CyberdyneRagAdapter(config.rag_base_url, shared_http(), rag_token)
        else:
            from cyberarche.application.testing.fakes import InMemoryRag

            rag = InMemoryRag()

    crdt_engine = PycrdtEngine()
    return Container(
        config=config,
        token_port=token_port,
        service_tokens=service_tokens,
        authorization=authorization,
        workspaces=workspaces,
        documents=documents,
        snapshots=snapshots,
        memberships=memberships,
        update_log=update_log,
        crdt_engine=crdt_engine,
        ingestions=ingestions,
        rag=rag,
        use_cases=_build_use_cases(
            workspaces,
            documents,
            snapshots,
            memberships,
            update_log,
            crdt_engine,
            ingestions,
            rag,
            clock,
            ids,
        ),
        _closers=closers,
    )
