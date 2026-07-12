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
from cyberarche.domain.ids import DocumentId, TenantId, UserId


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


async def test_insert_blocks_splits_a_markdown_blob_paragraph(mcp_setup):
    # A model that dumps "## heading" + a ```fence``` into one paragraph must
    # land as real heading/code blocks, not raw markdown text (regression).
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

    await client.call_tool(
        "insert_blocks",
        {
            "document_id": created["id"],
            "blocks": [
                {
                    "type": "paragraph",
                    "data": {
                        "text": "## Example (Python):\n```python\nprint(1)\n```"
                    },
                }
            ],
        },
    )

    read = data(await client.call_tool("read_document", {"document_id": created["id"]}))
    types = [b["type"] for b in read["blocks"]]
    assert types == ["heading", "code"]
    assert read["blocks"][0]["data"] == {"text": "Example (Python):", "level": 2}
    assert read["blocks"][1]["data"]["language"] == "python"


async def test_web_tools_absent_when_dao_unconfigured(mcp_setup):
    client, holder, _ = mcp_setup
    holder.use("alice-token")
    tools = {t.name for t in await client.list_tools()}
    assert "web_search" not in tools and "youtube_transcript" not in tools


async def test_web_search_and_transcript_forward_the_caller_bearer():
    from cyberarche.application.testing.fakes import ScriptedWebMedia

    web_media = ScriptedWebMedia()
    container = await build_container(
        WiringConfig(backend="memory"),
        token_port=StaticTokenPort({}),
        web_media=web_media,
    )
    holder = TokenHolder()

    async def resolver() -> CallerContext:
        caller = CALLERS.get(holder.token or "")
        if caller is None:
            raise NotAuthenticated("missing or invalid token")
        return caller

    def bearer() -> str:
        if not holder.token:
            raise NotAuthenticated("missing bearer token")
        return holder.token

    server = build_mcp_server(
        container, caller_resolver=resolver, bearer_resolver=bearer
    )
    async with Client(server) as client:
        holder.use("alice-token")
        tools = {t.name for t in await client.list_tools()}
        assert {"web_search", "youtube_transcript"} <= tools

        results = data(await client.call_tool("web_search", {"query": "cyberdyne"}))
        assert web_media.tokens == ["alice-token"]  # caller bearer forwarded
        assert results[0]["url"] == "https://a.test/1"

        transcript = data(
            await client.call_tool("youtube_transcript", {"video": "abc"})
        )
        assert transcript["text"].startswith("Hello")
        assert web_media.transcripts == ["abc"]

        # Unauthenticated call is denied.
        holder.use(None)
        with pytest.raises(ToolError):
            await client.call_tool("web_search", {"query": "x"})
    await container.aclose()


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
    teamspace = await container.use_cases.teamspaces.create(alice, workspace.id, name="Team")
    document = await container.use_cases.documents.create(
        alice, workspace_id=workspace.id, title="Locked", teamspace_id=teamspace.id
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



async def test_insert_blocks_at_a_position_over_mcp(mcp_setup):
    client, holder, container = mcp_setup
    workspace = await container.use_cases.workspaces.create(CALLERS["alice-token"], name="WS")
    holder.use("alice-token")
    doc = data(await client.call_tool("create_document", {"workspace_id": workspace.id, "title": "D"}))
    await client.call_tool("insert_blocks", {
        "document_id": doc["id"],
        "blocks": [{"id": "b1", "type": "paragraph", "data": {"text": "first"}},
                   {"id": "b2", "type": "paragraph", "data": {"text": "third"}}],
    })

    # Insert after b1 -> lands between b1 and b2.
    result = data(await client.call_tool("insert_blocks", {
        "document_id": doc["id"],
        "blocks": [{"id": "mid", "type": "paragraph", "data": {"text": "second"}}],
        "after_block_id": "b1",
    }))
    assert result == {"inserted": 1}

    read = data(await client.call_tool("read_document", {"document_id": doc["id"]}))
    assert [b["id"] for b in read["blocks"]] == ["b1", "mid", "b2"]


async def test_replace_block_over_mcp(mcp_setup):
    client, holder, container = mcp_setup
    workspace = await container.use_cases.workspaces.create(CALLERS["alice-token"], name="WS")
    holder.use("alice-token")
    doc = data(await client.call_tool("create_document", {"workspace_id": workspace.id, "title": "D"}))
    await client.call_tool("insert_blocks", {
        "document_id": doc["id"],
        "blocks": [{"id": "b1", "type": "paragraph", "data": {"text": "plain"}}],
    })

    result = data(await client.call_tool("replace_block", {
        "document_id": doc["id"],
        "block_id": "b1",
        "block": {"type": "heading", "data": {"text": "Title", "level": 2}},
    }))
    assert result == {"replaced": "b1"}

    read = data(await client.call_tool("read_document", {"document_id": doc["id"]}))
    assert read["blocks"][0]["id"] == "b1"
    assert read["blocks"][0]["type"] == "heading"


async def test_view_only_caller_cannot_replace_over_mcp(mcp_setup):
    from datetime import UTC, datetime

    from cyberarche.domain.memberships import Role, WorkspaceMembership

    client, holder, container = mcp_setup
    alice = CALLERS["alice-token"]
    viewer = CallerContext(user_id=UserId("dave"), tenant_id=TenantId("acme"))
    CALLERS["dave-token"] = viewer
    workspace = await container.use_cases.workspaces.create(alice, name="WS")
    doc = await container.use_cases.documents.create(alice, workspace_id=workspace.id, title="Locked")
    await container.use_cases.agent.apply_blocks(
        alice, doc.id, [{"id": "b1", "type": "paragraph", "data": {"text": "x"}}]
    )
    await container.memberships.add_workspace_member(
        WorkspaceMembership(
            workspace_id=workspace.id, user_id=viewer.user_id,
            role=Role.VIEWER, granted_at=datetime.now(UTC),
        )
    )

    holder.use("dave-token")
    with pytest.raises(ToolError):
        await client.call_tool("replace_block", {
            "document_id": doc.id, "block_id": "b1",
            "block": {"type": "paragraph", "data": {"text": "hijacked"}},
        })

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


async def test_workspace_and_teamspace_discovery_over_mcp(mcp_setup):
    client, holder, container = mcp_setup
    alice = CALLERS["alice-token"]
    workspace = await container.use_cases.workspaces.create(alice, name="Acme")
    teamspace = await container.use_cases.teamspaces.create(
        alice, workspace.id, name="Engineering"
    )

    holder.use("alice-token")
    workspaces = data(await client.call_tool("list_workspaces", {}))
    assert {"id": workspace.id, "name": "Acme"} in workspaces

    teamspaces = data(
        await client.call_tool("list_teamspaces", {"workspace_id": workspace.id})
    )
    assert {"id": teamspace.id, "name": "Engineering"} in teamspaces

    # A document can now be placed in that teamspace over MCP.
    created = data(
        await client.call_tool(
            "create_document",
            {
                "workspace_id": workspace.id,
                "title": "Roadmap",
                "teamspace_id": teamspace.id,
            },
        )
    )
    doc = await container.use_cases.documents.get(alice, DocumentId(created["id"]))
    assert doc.teamspace_id == teamspace.id
