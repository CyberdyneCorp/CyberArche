"""External MCP ports (external-mcp-connectors spec)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from cyberarche.domain.connectors import Connector
from cyberarche.domain.ids import ConnectorId, TenantId, WorkspaceId


@dataclass(frozen=True, slots=True)
class ExternalTool:
    name: str
    description: str
    parameters: dict[str, Any]


class McpClientPort(Protocol):
    """Driving client for external MCP servers. `credentials` is the secret
    presented as a bearer token (may be empty for open servers)."""

    async def list_tools(self, endpoint: str, credentials: str) -> list[ExternalTool]:
        """Connect + handshake; raises on unreachable/failed handshake."""
        ...

    async def call_tool(
        self, endpoint: str, credentials: str, tool: str, arguments: dict
    ) -> str: ...


class SecretBoxPort(Protocol):
    """Envelope encryption for connector credentials at rest."""

    def encrypt(self, plaintext: str) -> bytes: ...

    def decrypt(self, ciphertext: bytes) -> str: ...


class ConnectorRepository(Protocol):
    async def add(self, connector: Connector, credentials_encrypted: bytes) -> None: ...

    async def get(
        self, tenant_id: TenantId, connector_id: ConnectorId
    ) -> Connector | None: ...

    async def credentials(self, connector_id: ConnectorId) -> bytes: ...

    async def list_for_workspace(
        self, tenant_id: TenantId, workspace_id: WorkspaceId
    ) -> list[Connector]: ...

    async def by_slug(
        self, tenant_id: TenantId, workspace_id: WorkspaceId, slug: str
    ) -> Connector | None: ...

    async def update(self, connector: Connector) -> None: ...

    async def delete(self, tenant_id: TenantId, connector_id: ConnectorId) -> None: ...
