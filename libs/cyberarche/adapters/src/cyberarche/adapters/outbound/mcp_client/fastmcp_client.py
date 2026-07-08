"""McpClientPort adapter over fastmcp.Client (Streamable HTTP transport)."""

from __future__ import annotations

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

from cyberarche.application.ports.mcp import ExternalTool


def _transport(endpoint: str, credentials: str) -> StreamableHttpTransport:
    headers = {"Authorization": f"Bearer {credentials}"} if credentials else {}
    return StreamableHttpTransport(endpoint, headers=headers)


class FastMcpClientAdapter:
    async def list_tools(self, endpoint: str, credentials: str) -> list[ExternalTool]:
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
        async with Client(_transport(endpoint, credentials)) as client:
            result = await client.call_tool(tool, arguments)
        parts = [
            block.text for block in result.content if getattr(block, "text", None)
        ]
        return "\n".join(parts)
