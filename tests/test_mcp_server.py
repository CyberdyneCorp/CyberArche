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


# ---- the REAL HTTP caller resolver (mcp-server / auth-integration) ----------
#
# Every test above injects a fake resolver, so the production auth path — parse
# the Bearer header, verify it through container.token_port — was never run.
# These exercise the real _http_caller_resolver with a synthetic HTTP request,
# including an API key flowing through the composite verifier.


def _request_with_auth(header_value: str | None):
    from starlette.requests import Request

    headers = [(b"authorization", header_value.encode())] if header_value else []
    return Request(
        {"type": "http", "http_version": "1.1", "method": "POST", "scheme": "http",
         "path": "/mcp", "raw_path": b"/mcp", "query_string": b"",
         "headers": headers, "client": None, "server": None, "root_path": ""}
    )


async def _resolve_with(container, header_value: str | None):
    """Run the real resolver as if an HTTP request with this header were active."""
    from cyberarche.adapters.inbound.mcp.server import _http_caller_resolver
    from fastmcp.server import dependencies as dep

    resolve = _http_caller_resolver(container)
    token = dep._current_http_request.set(_request_with_auth(header_value))
    try:
        return await resolve()
    finally:
        dep._current_http_request.reset(token)


async def test_real_resolver_verifies_a_bearer_token_through_the_token_port():
    from cyberarche.application.ports.identity import Claims

    inner = StaticTokenPort(
        {"good-jwt": Claims(subject="alice", tenant_id="acme", email="a@acme.test")}
    )
    container = await build_container(WiringConfig(backend="memory"), token_port=inner)
    try:
        caller = await _resolve_with(container, "Bearer good-jwt")
        assert caller.user_id == "alice"
        assert caller.tenant_id == "acme"
    finally:
        await container.aclose()


async def test_real_resolver_rejects_missing_and_malformed_headers():
    container = await build_container(
        WiringConfig(backend="memory"), token_port=StaticTokenPort({})
    )
    try:
        for header in (None, "", "good-jwt", "Basic good-jwt", "Bearer   "):
            with pytest.raises(NotAuthenticated):
                await _resolve_with(container, header)
    finally:
        await container.aclose()


async def test_real_resolver_rejects_an_unknown_token():
    container = await build_container(
        WiringConfig(backend="memory"), token_port=StaticTokenPort({})
    )
    try:
        with pytest.raises(NotAuthenticated):
            await _resolve_with(container, "Bearer not-a-real-token")
    finally:
        await container.aclose()


async def test_real_resolver_accepts_an_api_key_and_rejects_it_once_revoked():
    # Mint through the container's own use case so the key lands in the repo the
    # container's CompositeTokenVerifier actually checks (build_container wraps
    # any injected token_port in its own composite over its own key repo).
    from tests.conftest import caller

    container = await build_container(
        WiringConfig(backend="memory"), token_port=StaticTokenPort({})
    )
    try:
        alice = caller("alice", "acme")
        created = await container.use_cases.api_keys.create(alice, name="claude-desktop")
        secret = created.secret  # shown once

        caller_ctx = await _resolve_with(container, f"Bearer {secret}")
        assert caller_ctx.user_id == "alice"  # authenticates as the key's owner

        await container.use_cases.api_keys.revoke(alice, created.key.id)
        with pytest.raises(NotAuthenticated):
            await _resolve_with(container, f"Bearer {secret}")
    finally:
        await container.aclose()
