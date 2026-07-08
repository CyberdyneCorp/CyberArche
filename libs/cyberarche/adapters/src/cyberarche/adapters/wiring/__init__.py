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
from cyberarche.application.use_cases import UseCases
from cyberarche.application.use_cases.documents import DocumentUseCases
from cyberarche.application.use_cases.snapshots import SnapshotUseCases
from cyberarche.application.use_cases.workspaces import WorkspaceUseCases
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
    clock,
    ids,
) -> UseCases:
    access = AccessControl(memberships)
    return UseCases(
        workspaces=WorkspaceUseCases(workspaces, memberships, clock, ids),
        documents=DocumentUseCases(documents, access, clock, ids),
        snapshots=SnapshotUseCases(snapshots, documents, access, clock, ids),
    )


async def build_container(
    config: WiringConfig,
    *,
    token_port: TokenPort | None = None,
) -> Container:
    """Build the container. `token_port` is injectable for tests/sample runtime."""
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

        pool = await asyncpg.create_pool(config.database_url)
        closers.append(pool.close)
        workspaces = PostgresWorkspaceRepository(pool)
        documents = PostgresDocumentRepository(pool)
        snapshots = PostgresSnapshotRepository(pool)
        memberships = PostgresMembershipRepository(pool)
    else:
        from cyberarche.application.testing.fakes import (
            InMemoryDocumentRepository,
            InMemoryMembershipRepository,
            InMemorySnapshotRepository,
            InMemoryWorkspaceRepository,
        )

        workspaces = InMemoryWorkspaceRepository()
        documents = InMemoryDocumentRepository()
        snapshots = InMemorySnapshotRepository()
        memberships = InMemoryMembershipRepository()

    service_tokens: ServiceTokenPort | None = None
    authorization: AuthorizationPort | None = None
    if token_port is None:
        if not config.auth_base_url:
            raise ValueError(
                "auth_base_url is required unless a token_port is injected"
            )
        http = httpx.AsyncClient(timeout=10.0)
        closers.append(http.aclose)
        auth_config = CyberdyneAuthConfig(
            base_url=config.auth_base_url,
            client_id=config.auth_client_id,
            client_secret=config.auth_client_secret,
            audience=config.auth_audience,
            tenant_claim=config.auth_tenant_claim,
        )
        credentials = ClientCredentialsTokenSource(auth_config, http)
        token_port = JwksTokenVerifier(auth_config, http, credentials)
        service_tokens = credentials
        authorization = IamAuthorization(auth_config, http, credentials)

    return Container(
        config=config,
        token_port=token_port,
        service_tokens=service_tokens,
        authorization=authorization,
        workspaces=workspaces,
        documents=documents,
        snapshots=snapshots,
        memberships=memberships,
        use_cases=_build_use_cases(
            workspaces, documents, snapshots, memberships, clock, ids
        ),
        _closers=closers,
    )
