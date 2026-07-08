"""mcp-server spec: tools enforce the same permissions as HTTP/realtime.

Runs the FastMCP server in-memory over the same container the HTTP tests
use, with an injected caller resolver simulating per-call token auth.
"""

from __future__ import annotations

import base64

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from cyberarche.adapters.inbound.mcp.server import build_mcp_server
from cyberarche.adapters.wiring import WiringConfig, build_container
from cyberarche.application.kernel import CallerContext
from cyberarche.application.testing.fakes import StaticTokenPort
from cyberarche.domain.errors import NotAuthenticated
from cyberarche.domain.ids import TenantId, UserId


class TokenHolder:
    """Simulates the per-request bearer token of a live MCP connection."""

    def __init__(self) -> None:
        self.token: str | None = None

    def use(self, token: str | None) -> None:
        self.token = token


CALLERS = {
    "alice-token": CallerContext(user_id=UserId("alice"), tenant_id=TenantId("acme")),
    "mallory-token": CallerContext(
        user_id=UserId("mallory"), tenant_id=TenantId("globex")
    ),
}


@pytest.fixture
async def mcp_setup():
    container = await build_container(
        WiringConfig(backend="memory"), token_port=StaticTokenPort({})
    )
    holder = TokenHolder()

    async def resolver() -> CallerContext:
        caller = CALLERS.get(holder.token or "")
        if caller is None:
            raise NotAuthenticated("missing or invalid token")
        return caller

    server = build_mcp_server(container, caller_resolver=resolver)
    async with Client(server) as client:
        yield client, holder, container
    await container.aclose()


def data(result):
    return result.data


async def test_unauthenticated_tool_call_is_denied(mcp_setup):
    client, holder, _ = mcp_setup
    holder.use(None)
    with pytest.raises(ToolError):
        await client.call_tool("search_documents", {"query": "x"})


async def test_search_and_read_are_tenant_scoped(mcp_setup):
    client, holder, container = mcp_setup
    workspace = await container.use_cases.workspaces.create(
        CALLERS["alice-token"], name="WS"
    )
    document = await container.use_cases.documents.create(
        CALLERS["alice-token"], workspace_id=workspace.id, title="Plan Alpha"
    )

    holder.use("alice-token")
    results = data(await client.call_tool("search_documents", {"query": "plan"}))
    assert [r["id"] for r in results] == [document.id]

    # Mallory (other tenant) sees nothing and cannot read.
    holder.use("mallory-token")
    assert data(await client.call_tool("search_documents", {"query": "plan"})) == []
    with pytest.raises(ToolError):
        await client.call_tool("read_document", {"document_id": document.id})


async def test_insert_blocks_flows_through_crdt_and_read_returns_them(mcp_setup):
    client, holder, container = mcp_setup
    workspace = await container.use_cases.workspaces.create(
        CALLERS["alice-token"], name="WS"
    )
    holder.use("alice-token")
    created = data(
        await client.call_tool(
            "create_document", {"workspace_id": workspace.id, "title": "Doc"}
        )
    )

    inserted = data(
        await client.call_tool(
            "insert_blocks",
            {
                "document_id": created["id"],
                "blocks": [
                    {"id": "b1", "type": "paragraph", "data": {"text": "via MCP"}}
                ],
            },
        )
    )
    assert inserted == {"inserted": 1}

    read = data(await client.call_tool("read_document", {"document_id": created["id"]}))
    assert read["blocks"][0]["data"]["text"] == "via MCP"
    # The edit went through the shared update log (same channel as humans).
    updates = await container.update_log.list_for_document(created["id"])
    assert updates[-1].origin == "agent:alice"


async def test_knowledge_tools_ingest_and_query(mcp_setup):
    client, holder, container = mcp_setup
    workspace = await container.use_cases.workspaces.create(
        CALLERS["alice-token"], name="WS"
    )
    holder.use("alice-token")

    ingested = data(
        await client.call_tool(
            "ingest_file",
            {
                "workspace_id": workspace.id,
                "filename": "notes.md",
                "content_base64": base64.b64encode(b"# notes").decode(),
            },
        )
    )
    assert ingested["status"] in ("processing", "completed")

    queried = data(
        await client.call_tool(
            "rag_query", {"workspace_id": workspace.id, "query": "notes"}
        )
    )
    assert "notes.md" in queried["result"]

    # Mallory cannot query alice's workspace knowledge.
    holder.use("mallory-token")
    with pytest.raises(ToolError):
        await client.call_tool(
            "rag_query", {"workspace_id": workspace.id, "query": "notes"}
        )


async def test_parity_all_surfaces_deny_the_same_edit(mcp_setup):
    """permissions-sharing spec: HTTP, realtime, and MCP deny identically."""
    client, holder, container = mcp_setup
    from datetime import UTC, datetime

    from cyberarche.domain.errors import NotAuthorized
    from cyberarche.domain.memberships import Role, WorkspaceMembership

    alice, viewer = CALLERS["alice-token"], CallerContext(
        user_id=UserId("carol"), tenant_id=TenantId("acme")
    )
    CALLERS["carol-token"] = viewer
    workspace = await container.use_cases.workspaces.create(alice, name="WS")
    document = await container.use_cases.documents.create(
        alice, workspace_id=workspace.id, title="Locked"
    )
    await container.memberships.add_workspace_member(
        WorkspaceMembership(
            workspace_id=workspace.id,
            user_id=viewer.user_id,
            role=Role.VIEWER,
            granted_at=datetime.now(UTC),
        )
    )
    block = {"id": "x", "type": "paragraph", "data": {"text": "sneak"}}

    # Use-case surface (drives HTTP + realtime): denied.
    with pytest.raises(NotAuthorized):
        await container.use_cases.agent.apply_blocks(viewer, document.id, [block])
    # MCP surface: denied identically.
    holder.use("carol-token")
    with pytest.raises(ToolError):
        await client.call_tool(
            "insert_blocks", {"document_id": document.id, "blocks": [block]}
        )
    # But reading is allowed on every surface (viewer role).
    read = data(await client.call_tool("read_document", {"document_id": document.id}))
    assert read["title"] == "Locked"
