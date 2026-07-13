"""McpClientPort adapter over fastmcp.Client (Streamable HTTP transport)."""

from __future__ import annotations

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

from cyberarche.adapters.outbound.mcp_client.ssrf_guard import validate_endpoint
from cyberarche.application.ports.mcp import ExternalTool


def _transport(endpoint: str, credentials: str) -> StreamableHttpTransport:
    headers = {"Authorization": f"Bearer {credentials}"} if credentials else {}
    return StreamableHttpTransport(endpoint, headers=headers)


class FastMcpClientAdapter:
    def __init__(self, *, allow_private_networks: bool = False) -> None:
        # Private/loopback targets are permitted only in local/dev, where
        # connectors legitimately point at 127.0.0.1 test fixtures.
        self._allow_private_networks = allow_private_networks

    def _guard(self, endpoint: str) -> None:
        # Re-validated on every fetch (register, tools, call), not only at
        # registration, so a stored or DNS-rebound endpoint can't slip through.
        validate_endpoint(
            endpoint, allow_private_networks=self._allow_private_networks
        )

    async def list_tools(self, endpoint: str, credentials: str) -> list[ExternalTool]:
        self._guard(endpoint)
        async with Client(_transport(endpoint, credentials)) as client:
            tools = await client.list_tools()
        return [
            ExternalTool(
                name=tool.name,
                description=tool.description or "",
                parameters=tool.inputSchema or {"type": "object", "properties": {}},
            )
            for tool in tools
        ]

    async def call_tool(
        self, endpoint: str, credentials: str, tool: str, arguments: dict
    ) -> str:
        self._guard(endpoint)
        async with Client(_transport(endpoint, credentials)) as client:
            result = await client.call_tool(tool, arguments)
        parts = [
            block.text for block in result.content if getattr(block, "text", None)
        ]
        return "\n".join(parts)
