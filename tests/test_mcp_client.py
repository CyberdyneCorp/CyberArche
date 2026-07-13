"""FastMcpClientAdapter: outbound MCP client over Streamable HTTP.

Runs the adapter against a real in-memory FastMCP server by patching the
module's StreamableHttpTransport factory, so the endpoint/credentials
plumbing and the result mapping are exercised end-to-end. The branches
that real fastmcp servers never produce (missing input schema, custom
result shapes) are covered with a stub Client.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import ImageContent, TextContent

from cyberarche.adapters.outbound.mcp_client import fastmcp_client
from cyberarche.adapters.outbound.mcp_client.fastmcp_client import (
    FastMcpClientAdapter,
    _transport,
)

ENDPOINT = "https://tools.example.test/mcp"


# ---------------------------------------------------------------------------
# _transport: bearer-header construction


def test_transport_sets_bearer_header_from_credentials():
    transport = _transport(ENDPOINT, "s3cret")
    assert transport.url == ENDPOINT
    assert transport.headers == {"Authorization": "Bearer s3cret"}


def test_transport_omits_authorization_when_credentials_empty():
    transport = _transport(ENDPOINT, "")
    assert transport.url == ENDPOINT
    assert transport.headers == {}


# ---------------------------------------------------------------------------
# Adapter against a real in-memory FastMCP server


def _build_external_server() -> FastMCP:
    server = FastMCP("external")

    @server.tool
    def echo(text: str) -> str:
        """Echo the text back."""
        return f"echo: {text}"

    @server.tool
    def no_doc(x: int) -> int:
        return x

    @server.tool
    def mixed_content() -> list:
        return [
            TextContent(type="text", text="first"),
            ImageContent(type="image", data="aGk=", mimeType="image/png"),
            TextContent(type="text", text="second"),
        ]

    @server.tool
    def image_only() -> ImageContent:
        return ImageContent(type="image", data="aGk=", mimeType="image/png")

    @server.tool
    def boom() -> str:
        raise RuntimeError("kaput")

    return server


@pytest.fixture
def external_server(monkeypatch):
    """Route the adapter's Streamable HTTP transport to an in-memory server,
    recording what `_transport` was asked to build."""
    server = _build_external_server()
    captured: dict = {}

    def fake_transport(url, headers=None):
        captured["url"] = url
        captured["headers"] = headers
        return server

    monkeypatch.setattr(fastmcp_client, "StreamableHttpTransport", fake_transport)
    return captured


async def test_list_tools_maps_name_description_and_schema(external_server):
    tools = await FastMcpClientAdapter(allow_private_networks=True).list_tools(ENDPOINT, "token")

    by_name = {tool.name: tool for tool in tools}
    echo = by_name["echo"]
    assert echo.description == "Echo the text back."
    assert echo.parameters["properties"]["text"] == {"type": "string"}
    assert echo.parameters["required"] == ["text"]


async def test_list_tools_defaults_missing_description_to_empty(external_server):
    tools = await FastMcpClientAdapter(allow_private_networks=True).list_tools(ENDPOINT, "token")

    by_name = {tool.name: tool for tool in tools}
    assert by_name["no_doc"].description == ""


async def test_list_tools_sends_credentials_as_bearer(external_server):
    await FastMcpClientAdapter(allow_private_networks=True).list_tools(ENDPOINT, "s3cret")

    assert external_server["url"] == ENDPOINT
    assert external_server["headers"] == {"Authorization": "Bearer s3cret"}


async def test_list_tools_open_server_sends_no_auth_header(external_server):
    await FastMcpClientAdapter(allow_private_networks=True).list_tools(ENDPOINT, "")

    assert external_server["headers"] == {}


async def test_call_tool_forwards_arguments_and_returns_text(external_server):
    result = await FastMcpClientAdapter(allow_private_networks=True).call_tool(
        ENDPOINT, "token", "echo", {"text": "hi"}
    )

    assert result == "echo: hi"
    assert external_server["url"] == ENDPOINT
    assert external_server["headers"] == {"Authorization": "Bearer token"}


async def test_call_tool_joins_text_blocks_and_skips_non_text(external_server):
    result = await FastMcpClientAdapter(allow_private_networks=True).call_tool(ENDPOINT, "token", "mixed_content", {})

    assert result == "first\nsecond"


async def test_call_tool_returns_empty_string_when_no_text_content(external_server):
    result = await FastMcpClientAdapter(allow_private_networks=True).call_tool(ENDPOINT, "token", "image_only", {})

    assert result == ""


async def test_call_tool_propagates_remote_tool_errors(external_server):
    with pytest.raises(ToolError):
        await FastMcpClientAdapter(allow_private_networks=True).call_tool(ENDPOINT, "token", "boom", {})


async def test_call_tool_unknown_tool_raises(external_server):
    with pytest.raises(ToolError):
        await FastMcpClientAdapter(allow_private_networks=True).call_tool(ENDPOINT, "token", "nope", {})


# ---------------------------------------------------------------------------
# Branches real servers never emit, via a stub Client


def _stub_client(monkeypatch, *, tools=(), result=None):
    class StubClient:
        def __init__(self, transport):
            self.transport = transport

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

        async def list_tools(self):
            return list(tools)

        async def call_tool(self, tool, arguments):
            return result

    monkeypatch.setattr(fastmcp_client, "Client", StubClient)


async def test_list_tools_defaults_missing_input_schema(monkeypatch):
    _stub_client(
        monkeypatch,
        tools=[SimpleNamespace(name="bare", description=None, inputSchema=None)],
    )

    (tool,) = await FastMcpClientAdapter(allow_private_networks=True).list_tools(ENDPOINT, "token")

    assert tool.name == "bare"
    assert tool.description == ""
    assert tool.parameters == {"type": "object", "properties": {}}


async def test_call_tool_skips_blocks_with_empty_text(monkeypatch):
    _stub_client(
        monkeypatch,
        result=SimpleNamespace(
            content=[
                SimpleNamespace(text="kept"),
                SimpleNamespace(text=""),
                SimpleNamespace(text=None),
                SimpleNamespace(data="not-text"),
            ]
        ),
    )

    result = await FastMcpClientAdapter(allow_private_networks=True).call_tool(ENDPOINT, "token", "any", {})

    assert result == "kept"


async def test_call_tool_empty_content_returns_empty_string(monkeypatch):
    _stub_client(monkeypatch, result=SimpleNamespace(content=[]))

    result = await FastMcpClientAdapter(allow_private_networks=True).call_tool(ENDPOINT, "token", "any", {})

    assert result == ""
