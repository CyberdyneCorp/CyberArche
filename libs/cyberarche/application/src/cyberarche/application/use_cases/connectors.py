"""External MCP connector use cases (external-mcp-connectors spec)."""

from __future__ import annotations

from cyberarche.application.authz import AccessControl
from cyberarche.application.kernel import CallerContext
from cyberarche.application.ports.llm import ToolSpec
from cyberarche.application.ports.mcp import (
    ConnectorRepository,
    McpClientPort,
    SecretBoxPort,
)
from cyberarche.application.ports.telemetry import ClockPort, IdPort
from cyberarche.domain.connectors import Connector, slugify, split_qualified
from cyberarche.domain.errors import Conflict, NotFound, ValidationFailed
from cyberarche.domain.ids import ConnectorId, WorkspaceId
from cyberarche.domain.memberships import Role


class ConnectorUseCases:
    def __init__(
        self,
        connectors: ConnectorRepository,
        client: McpClientPort,
        secrets: SecretBoxPort,
        access: AccessControl,
        clock: ClockPort,
        ids: IdPort,
    ) -> None:
        self._connectors = connectors
        self._client = client
        self._secrets = secrets
        self._access = access
        self._clock = clock
        self._ids = ids

    async def register(
        self,
        caller: CallerContext,
        workspace_id: WorkspaceId,
        *,
        name: str,
        endpoint: str,
        credentials: str = "",
    ) -> Connector:
        """Register an external MCP server for a workspace.

        The endpoint must complete an MCP handshake now (reject unreachable);
        credentials are envelope-encrypted at rest and never returned.
        """
        await self._access.require_workspace(caller, workspace_id, Role.OWNER)
        slug = slugify(name)
        existing = await self._connectors.by_slug(caller.tenant_id, workspace_id, slug)
        if existing is not None:
            raise Conflict(f"a connector named {slug!r} already exists here")
        try:
            await self._client.list_tools(endpoint, credentials)
        except Exception as error:
            raise ValidationFailed(
                f"MCP handshake with {endpoint} failed: {error}"
            ) from error
        connector = Connector(
            id=ConnectorId(self._ids.new_id()),
            tenant_id=caller.tenant_id,
            workspace_id=workspace_id,
            name=name,
            slug=slug,
            endpoint=endpoint,
            enabled=True,
            created_by=caller.user_id,
            created_at=self._clock.now(),
        )
        await self._connectors.add(connector, self._secrets.encrypt(credentials))
        return connector

    async def list(
        self, caller: CallerContext, workspace_id: WorkspaceId
    ) -> list[Connector]:
        """Connector metadata only — secrets are never returned."""
        await self._access.require_workspace(caller, workspace_id, Role.VIEWER)
        return await self._connectors.list_for_workspace(caller.tenant_id, workspace_id)

    async def set_enabled(
        self, caller: CallerContext, connector_id: ConnectorId, *, enabled: bool
    ) -> Connector:
        connector = await self._get(caller, connector_id)
        await self._access.require_workspace(caller, connector.workspace_id, Role.OWNER)
        updated = connector.set_enabled(enabled)
        await self._connectors.update(updated)
        return updated

    async def remove(self, caller: CallerContext, connector_id: ConnectorId) -> None:
        connector = await self._get(caller, connector_id)
        await self._access.require_workspace(caller, connector.workspace_id, Role.OWNER)
        await self._connectors.delete(caller.tenant_id, connector_id)

    async def tools(
        self, caller: CallerContext, workspace_id: WorkspaceId
    ) -> list[ToolSpec]:
        """Namespaced tools of the workspace's ENABLED connectors, with the
        connector origin visible in the description."""
        await self._access.require_workspace(caller, workspace_id, Role.VIEWER)
        specs: list[ToolSpec] = []
        for connector in await self._connectors.list_for_workspace(
            caller.tenant_id, workspace_id
        ):
            if not connector.enabled:
                continue
            credentials = self._secrets.decrypt(
                await self._connectors.credentials(connector.id)
            )
            for tool in await self._client.list_tools(connector.endpoint, credentials):
                specs.append(
                    ToolSpec(
                        name=connector.qualified(tool.name),
                        description=f"[external: {connector.name}] {tool.description}",
                        parameters=tool.parameters,
                    )
                )
        return specs

    async def call(
        self,
        caller: CallerContext,
        workspace_id: WorkspaceId,
        *,
        qualified_name: str,
        arguments: dict,
    ) -> str:
        """Dispatch a namespaced tool call to its connector (enabled only)."""
        await self._access.require_workspace(caller, workspace_id, Role.VIEWER)
        parts = split_qualified(qualified_name)
        if parts is None:
            raise ValidationFailed(f"not a connector-qualified tool: {qualified_name}")
        slug, tool_name = parts
        connector = await self._connectors.by_slug(caller.tenant_id, workspace_id, slug)
        if connector is None or not connector.enabled:
            raise NotFound(f"no enabled connector {slug!r} in this workspace")
        credentials = self._secrets.decrypt(
            await self._connectors.credentials(connector.id)
        )
        return await self._client.call_tool(
            connector.endpoint, credentials, tool_name, arguments
        )

    async def _get(
        self, caller: CallerContext, connector_id: ConnectorId
    ) -> Connector:
        connector = await self._connectors.get(caller.tenant_id, connector_id)
        if connector is None:
            raise NotFound("connector not found")
        return connector
