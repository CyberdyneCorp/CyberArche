"""external-mcp-connectors spec: registration, secrets, namespacing, opt-in."""

from __future__ import annotations

import anyio
import pytest
from fastapi.testclient import TestClient

from cyberarche.adapters.wiring import WiringConfig, build_container
from cyberarche.api.bootstrap import create_app
from cyberarche.api.config import Settings
from cyberarche.application.ports.llm import LLMResponse, ToolCall
from cyberarche.application.ports.mcp import ExternalTool
from cyberarche.application.testing.fakes import FakeMcpClient, StaticTokenPort
from cyberarche.application.use_cases import UseCases
from cyberarche.domain.errors import Conflict, NotFound, ValidationFailed
from tests.conftest import TOKENS

SEARCH_TOOL = ExternalTool(
    name="search",
    description="Search things",
    parameters={"type": "object", "properties": {"q": {"type": "string"}}},
)


async def make_workspace(use_cases: UseCases, alice):
    return await use_cases.workspaces.create(alice, name="WS")


async def test_register_connector_exposes_its_tools(use_cases, mcp_client, alice):
    workspace = await make_workspace(use_cases, alice)
    mcp_client.servers["https://tools.example/mcp"] = [SEARCH_TOOL]

    connector = await use_cases.connectors.register(
        alice,
        workspace.id,
        name="Example Tools",
        endpoint="https://tools.example/mcp",
        credentials="s3cret",
    )

    assert connector.slug == "example-tools"
    tools = await use_cases.connectors.tools(alice, workspace.id)
    assert [t.name for t in tools] == ["example-tools__search"]
    assert "[external: Example Tools]" in tools[0].description  # origin visible


async def test_unreachable_endpoint_is_rejected(use_cases, alice):
    workspace = await make_workspace(use_cases, alice)
    with pytest.raises(ValidationFailed):
        await use_cases.connectors.register(
            alice, workspace.id, name="Ghost", endpoint="https://nowhere.example"
        )
    assert await use_cases.connectors.list(alice, workspace.id) == []


async def test_credentials_are_encrypted_at_rest_and_never_returned(
    use_cases, mcp_client, connector_repo, alice
):
    workspace = await make_workspace(use_cases, alice)
    mcp_client.servers["https://tools.example/mcp"] = [SEARCH_TOOL]

    connector = await use_cases.connectors.register(
        alice,
        workspace.id,
        name="Tools",
        endpoint="https://tools.example/mcp",
        credentials="super-secret",
    )

    stored = await connector_repo.credentials(connector.id)
    assert b"super-secret" not in stored  # not plaintext at rest
    from dataclasses import asdict

    listed = await use_cases.connectors.list(alice, workspace.id)
    assert "super-secret" not in str(asdict(listed[0]))
    # ...but calls present the decrypted credential to the external server.
    await use_cases.connectors.call(
        alice, workspace.id, qualified_name="tools__search", arguments={"q": "x"}
    )
    assert mcp_client.calls[0][1] == "super-secret"


async def test_same_tool_name_from_two_connectors_is_namespaced(
    use_cases, mcp_client, alice
):
    workspace = await make_workspace(use_cases, alice)
    mcp_client.servers["https://a.example/mcp"] = [SEARCH_TOOL]
    mcp_client.servers["https://b.example/mcp"] = [SEARCH_TOOL]
    await use_cases.connectors.register(
        alice, workspace.id, name="Alpha", endpoint="https://a.example/mcp"
    )
    await use_cases.connectors.register(
        alice, workspace.id, name="Beta", endpoint="https://b.example/mcp"
    )

    tools = await use_cases.connectors.tools(alice, workspace.id)
    assert sorted(t.name for t in tools) == ["alpha__search", "beta__search"]


async def test_duplicate_connector_name_conflicts(use_cases, mcp_client, alice):
    workspace = await make_workspace(use_cases, alice)
    mcp_client.servers["https://a.example/mcp"] = [SEARCH_TOOL]
    await use_cases.connectors.register(
        alice, workspace.id, name="Alpha", endpoint="https://a.example/mcp"
    )
    with pytest.raises(Conflict):
        await use_cases.connectors.register(
            alice, workspace.id, name="alpha", endpoint="https://a.example/mcp"
        )


async def test_disabled_connector_tools_are_not_offered_or_callable(
    use_cases, mcp_client, alice
):
    workspace = await make_workspace(use_cases, alice)
    mcp_client.servers["https://a.example/mcp"] = [SEARCH_TOOL]
    connector = await use_cases.connectors.register(
        alice, workspace.id, name="Alpha", endpoint="https://a.example/mcp"
    )

    await use_cases.connectors.set_enabled(alice, connector.id, enabled=False)

    assert await use_cases.connectors.tools(alice, workspace.id) == []
    with pytest.raises(NotFound):
        await use_cases.connectors.call(
            alice, workspace.id, qualified_name="alpha__search", arguments={}
        )


async def test_agent_calls_external_tool_through_connector(
    use_cases, mcp_client, llm, alice
):
    """ai-agent spec 8.5: the tool loop reaches external MCP tools."""
    workspace = await make_workspace(use_cases, alice)
    document = await use_cases.documents.create(
        alice, workspace_id=workspace.id, title="Doc"
    )
    mcp_client.servers["https://a.example/mcp"] = [SEARCH_TOOL]
    mcp_client.results["search"] = "external says: 42"
    await use_cases.connectors.register(
        alice, workspace.id, name="Alpha", endpoint="https://a.example/mcp"
    )
    llm._responses = [
        LLMResponse(
            text="",
            tool_calls=(
                ToolCall(id="c1", name="alpha__search", arguments={"q": "meaning"}),
            ),
        ),
        LLMResponse(text="The answer is 42", model="m"),
    ]

    answer = await use_cases.agent.ask(alice, document.id, instruction="?")

    assert answer.text == "The answer is 42"
    assert mcp_client.calls == [
        ("https://a.example/mcp", "", "search", {"q": "meaning"})
    ]
    # The external tool was offered to the model alongside built-ins.
    runs = await use_cases.agent.run_history(alice, document.id)
    assert runs[0].tools_used == ("alpha__search",)


async def test_non_owner_cannot_register_connector(
    use_cases, mcp_client, memberships, clock, alice
):
    from tests.conftest import caller
    from cyberarche.domain.errors import NotAuthorized
    from cyberarche.domain.memberships import Role, WorkspaceMembership

    editor = caller("bob", "acme")
    workspace = await make_workspace(use_cases, alice)
    await memberships.add_workspace_member(
        WorkspaceMembership(
            workspace_id=workspace.id,
            user_id=editor.user_id,
            role=Role.EDITOR,
            granted_at=clock.now(),
        )
    )
    mcp_client.servers["https://a.example/mcp"] = [SEARCH_TOOL]
    with pytest.raises(NotAuthorized):
        await use_cases.connectors.register(
            editor, workspace.id, name="Alpha", endpoint="https://a.example/mcp"
        )

# ---- document scope + per-session opt-in (extend-connector-scope-sessions) --


async def test_document_scoped_connector_is_active_only_on_its_document(
    use_cases, mcp_client, alice
):
    workspace = await make_workspace(use_cases, alice)
    doc_a = await use_cases.documents.create(alice, workspace_id=workspace.id, title="A")
    doc_b = await use_cases.documents.create(alice, workspace_id=workspace.id, title="B")
    mcp_client.servers["https://scoped.example/mcp"] = [SEARCH_TOOL]

    await use_cases.connectors.register(
        alice, workspace.id, name="Scoped", endpoint="https://scoped.example/mcp",
        document_id=doc_a.id,
    )

    on_a = await use_cases.connectors.tools(alice, workspace.id, document_id=doc_a.id)
    on_b = await use_cases.connectors.tools(alice, workspace.id, document_id=doc_b.id)
    assert [t.name for t in on_a] == ["scoped__search"]
    assert on_b == []  # not active on another document
    # And with no document context, a document-scoped connector is inactive.
    assert await use_cases.connectors.tools(alice, workspace.id) == []


async def test_workspace_scoped_connector_is_active_on_every_document(
    use_cases, mcp_client, alice
):
    workspace = await make_workspace(use_cases, alice)
    doc = await use_cases.documents.create(alice, workspace_id=workspace.id, title="A")
    mcp_client.servers["https://ws.example/mcp"] = [SEARCH_TOOL]
    await use_cases.connectors.register(
        alice, workspace.id, name="WideOpen", endpoint="https://ws.example/mcp"
    )

    on_doc = await use_cases.connectors.tools(alice, workspace.id, document_id=doc.id)
    assert [t.name for t in on_doc] == ["wideopen__search"]


async def test_session_opt_in_restricts_to_chosen_connectors(
    use_cases, mcp_client, alice
):
    workspace = await make_workspace(use_cases, alice)
    mcp_client.servers["https://a.example/mcp"] = [SEARCH_TOOL]
    mcp_client.servers["https://b.example/mcp"] = [SEARCH_TOOL]
    a = await use_cases.connectors.register(
        alice, workspace.id, name="Alpha", endpoint="https://a.example/mcp"
    )
    await use_cases.connectors.register(
        alice, workspace.id, name="Bravo", endpoint="https://b.example/mcp"
    )

    # No restriction: both connectors' tools are offered.
    everything = await use_cases.connectors.tools(alice, workspace.id)
    assert {t.name for t in everything} == {"alpha__search", "bravo__search"}

    # Session opts in to only Alpha.
    only_a = await use_cases.connectors.tools(
        alice, workspace.id, session_connectors={a.id}
    )
    assert [t.name for t in only_a] == ["alpha__search"]

    # And a call to the opted-out connector is refused.
    with pytest.raises(NotFound):
        await use_cases.connectors.call(
            alice, workspace.id, qualified_name="bravo__search", arguments={},
            session_connectors={a.id},
        )


async def test_agent_session_restricts_external_tools(use_cases, mcp_client, llm, alice):
    workspace = await make_workspace(use_cases, alice)
    document = await use_cases.documents.create(
        alice, workspace_id=workspace.id, title="Doc"
    )
    mcp_client.servers["https://a.example/mcp"] = [SEARCH_TOOL]
    mcp_client.servers["https://b.example/mcp"] = [SEARCH_TOOL]
    a = await use_cases.connectors.register(
        alice, workspace.id, name="Alpha", endpoint="https://a.example/mcp"
    )
    await use_cases.connectors.register(
        alice, workspace.id, name="Bravo", endpoint="https://b.example/mcp"
    )
    llm._responses = [LLMResponse(text="done", model="m")]

    await use_cases.agent.ask(
        alice, document.id, instruction="?", session_connectors={a.id}
    )

    # Only Alpha's tool was offered to the model this session.
    offered = {t.name for t in llm.tools_seen[0]}
    assert "alpha__search" in offered
    assert "bravo__search" not in offered


# ---- HTTP router -----------------------------------------------------------


def _auth(token: str = "alice-token") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def connector_api():
    """TestClient over an app whose container has a scripted MCP client."""

    fake_mcp = FakeMcpClient({"https://tools.example/mcp": [SEARCH_TOOL]})

    async def build():
        return await build_container(
            WiringConfig(backend="memory"),
            token_port=StaticTokenPort(dict(TOKENS)),
            mcp_client=fake_mcp,
        )

    container = anyio.run(build)
    settings = Settings(backend="memory", auth_base_url="", rag_base_url="")
    app = create_app(settings, container=container)
    with TestClient(app) as client:
        yield client


def _make_workspace_http(api) -> str:
    return api.post("/api/v1/workspaces", json={"name": "WS"}, headers=_auth()).json()[
        "id"
    ]


def test_connectors_router_roundtrip(connector_api):
    ws = _make_workspace_http(connector_api)
    base = f"/api/v1/workspaces/{ws}/connectors"

    created = connector_api.post(
        base,
        json={
            "name": "Example Tools",
            "endpoint": "https://tools.example/mcp",
            "credentials": "s3cret",
        },
        headers=_auth(),
    )
    assert created.status_code == 201
    connector = created.json()
    assert connector["name"] == "Example Tools"
    assert connector["slug"] == "example-tools"
    assert connector["endpoint"] == "https://tools.example/mcp"
    assert connector["enabled"] is True
    assert connector["created_by"] == "alice"
    assert "s3cret" not in created.text  # credentials never returned

    listed = connector_api.get(base, headers=_auth())
    assert listed.status_code == 200
    assert [c["id"] for c in listed.json()] == [connector["id"]]

    tools = connector_api.get(f"{base}/tools", headers=_auth())
    assert tools.status_code == 200
    assert [t["name"] for t in tools.json()] == ["example-tools__search"]
    assert "Search things" in tools.json()[0]["description"]

    disabled = connector_api.patch(
        f"{base}/{connector['id']}", json={"enabled": False}, headers=_auth()
    )
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False
    assert connector_api.get(f"{base}/tools", headers=_auth()).json() == []

    deleted = connector_api.delete(f"{base}/{connector['id']}", headers=_auth())
    assert deleted.status_code == 204
    assert connector_api.get(base, headers=_auth()).json() == []


def test_connectors_router_document_scoped_registration(connector_api):
    ws = _make_workspace_http(connector_api)
    doc = connector_api.post(
        "/api/v1/documents",
        json={"workspace_id": ws, "title": "Doc"},
        headers=_auth(),
    ).json()

    created = connector_api.post(
        f"/api/v1/workspaces/{ws}/connectors",
        json={
            "name": "Scoped",
            "endpoint": "https://tools.example/mcp",
            "document_id": doc["id"],
        },
        headers=_auth(),
    )
    assert created.status_code == 201
    # Without a document context, a document-scoped connector offers no tools.
    tools = connector_api.get(
        f"/api/v1/workspaces/{ws}/connectors/tools", headers=_auth()
    )
    assert tools.json() == []


def test_connectors_router_error_mapping(connector_api):
    ws = _make_workspace_http(connector_api)
    base = f"/api/v1/workspaces/{ws}/connectors"

    # Unreachable endpoint -> ValidationFailed -> 422.
    unreachable = connector_api.post(
        base,
        json={"name": "Ghost", "endpoint": "https://nowhere.example"},
        headers=_auth(),
    )
    assert unreachable.status_code == 422

    connector_api.post(
        base,
        json={"name": "Alpha", "endpoint": "https://tools.example/mcp"},
        headers=_auth(),
    )
    # Duplicate name -> Conflict -> 409.
    duplicate = connector_api.post(
        base,
        json={"name": "alpha", "endpoint": "https://tools.example/mcp"},
        headers=_auth(),
    )
    assert duplicate.status_code == 409

    # Unknown connector ids -> NotFound -> 404.
    assert (
        connector_api.patch(
            f"{base}/missing", json={"enabled": False}, headers=_auth()
        ).status_code
        == 404
    )
    assert connector_api.delete(f"{base}/missing", headers=_auth()).status_code == 404


def test_connectors_router_requires_auth_and_membership(connector_api):
    ws = _make_workspace_http(connector_api)
    base = f"/api/v1/workspaces/{ws}/connectors"

    # No token -> 401 before any use case runs.
    assert connector_api.get(base).status_code == 401
    # A caller outside the workspace cannot register -> 403.
    forbidden = connector_api.post(
        base,
        json={"name": "Alpha", "endpoint": "https://tools.example/mcp"},
        headers=_auth("mallory-token"),
    )
    assert forbidden.status_code == 403


# ---------------------------------------------------------------------------
# PostgresConnectorRepository: SQL adapter over a stubbed asyncpg pool.
# ---------------------------------------------------------------------------

from datetime import UTC, datetime

from cyberarche.adapters.outbound.postgres.connectors import (
    PostgresConnectorRepository,
)
from cyberarche.domain.connectors import Connector
from cyberarche.domain.ids import (
    ConnectorId,
    DocumentId,
    TenantId,
    UserId,
    WorkspaceId,
)

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


class _FakePool:
    """Stands in for asyncpg.Pool: records queries, returns canned rows."""

    def __init__(self, row=None, rows=None, value=None):
        self.row = row
        self.rows = rows or []
        self.value = value
        self.calls: list[tuple[str, tuple]] = []

    async def execute(self, query, *args):
        self.calls.append((query, args))
        return "OK"

    async def fetchrow(self, query, *args):
        self.calls.append((query, args))
        return self.row

    async def fetch(self, query, *args):
        self.calls.append((query, args))
        return self.rows

    async def fetchval(self, query, *args):
        self.calls.append((query, args))
        return self.value


def _connector(**kw) -> Connector:
    defaults = dict(
        id=ConnectorId("conn-1"),
        tenant_id=TenantId("acme"),
        workspace_id=WorkspaceId("ws-1"),
        name="Example Tools",
        slug="example-tools",
        endpoint="https://tools.example/mcp",
        enabled=True,
        created_by=UserId("alice"),
        created_at=_NOW,
        document_id=None,
    )
    defaults.update(kw)
    return Connector(**defaults)


def _connector_row(**kw) -> dict:
    row = dict(
        id="conn-1",
        tenant_id="acme",
        workspace_id="ws-1",
        name="Example Tools",
        slug="example-tools",
        endpoint="https://tools.example/mcp",
        enabled=True,
        created_by="alice",
        created_at=_NOW,
        document_id=None,
    )
    row.update(kw)
    return row


async def test_postgres_connector_add_inserts_every_column():
    pool = _FakePool()
    connector = _connector(document_id=DocumentId("doc-9"))

    await PostgresConnectorRepository(pool).add(connector, b"ciphertext")

    query, args = pool.calls[0]
    assert "INSERT INTO mcp_connectors" in query
    assert args == (
        "conn-1", "acme", "ws-1", "Example Tools", "example-tools",
        "https://tools.example/mcp", b"ciphertext", True, "alice", _NOW, "doc-9",
    )


async def test_postgres_connector_get_maps_row_and_scopes_by_tenant():
    pool = _FakePool(row=_connector_row(document_id="doc-9"))

    found = await PostgresConnectorRepository(pool).get(
        TenantId("acme"), ConnectorId("conn-1")
    )

    assert found == _connector(document_id=DocumentId("doc-9"))
    query, args = pool.calls[0]
    assert "tenant_id = $2" in query
    assert args == ("conn-1", "acme")


async def test_postgres_connector_get_returns_none_when_missing():
    repo = PostgresConnectorRepository(_FakePool(row=None))
    assert await repo.get(TenantId("acme"), ConnectorId("ghost")) is None


async def test_postgres_connector_row_without_document_maps_to_none():
    pool = _FakePool(row=_connector_row(document_id=None))
    found = await PostgresConnectorRepository(pool).get(
        TenantId("acme"), ConnectorId("conn-1")
    )
    assert found is not None and found.document_id is None


async def test_postgres_connector_credentials_returns_bytes():
    # asyncpg may hand back a non-bytes buffer; the adapter normalizes it.
    pool = _FakePool(value=memoryview(b"ciphertext"))

    stored = await PostgresConnectorRepository(pool).credentials(
        ConnectorId("conn-1")
    )

    assert stored == b"ciphertext"
    assert isinstance(stored, bytes)


async def test_postgres_connector_credentials_missing_raises_not_found():
    repo = PostgresConnectorRepository(_FakePool(value=None))
    with pytest.raises(NotFound):
        await repo.credentials(ConnectorId("ghost"))


async def test_postgres_connector_list_for_workspace_maps_all_rows():
    pool = _FakePool(
        rows=[
            _connector_row(),
            _connector_row(id="conn-2", slug="beta", document_id="doc-9"),
        ]
    )

    listed = await PostgresConnectorRepository(pool).list_for_workspace(
        TenantId("acme"), WorkspaceId("ws-1")
    )

    assert [c.id for c in listed] == ["conn-1", "conn-2"]
    assert listed[1].document_id == DocumentId("doc-9")
    query, args = pool.calls[0]
    assert "ORDER BY created_at" in query
    assert args == ("acme", "ws-1")


async def test_postgres_connector_list_for_workspace_empty():
    repo = PostgresConnectorRepository(_FakePool(rows=[]))
    assert await repo.list_for_workspace(TenantId("acme"), WorkspaceId("ws-1")) == []


async def test_postgres_connector_by_slug_found_and_missing():
    pool = _FakePool(row=_connector_row())
    found = await PostgresConnectorRepository(pool).by_slug(
        TenantId("acme"), WorkspaceId("ws-1"), "example-tools"
    )
    assert found == _connector()
    assert pool.calls[0][1] == ("acme", "ws-1", "example-tools")

    missing = PostgresConnectorRepository(_FakePool(row=None))
    assert (
        await missing.by_slug(TenantId("acme"), WorkspaceId("ws-1"), "ghost") is None
    )


async def test_postgres_connector_update_writes_name_and_enabled():
    pool = _FakePool()

    await PostgresConnectorRepository(pool).update(
        _connector(name="Renamed", enabled=False)
    )

    query, args = pool.calls[0]
    assert "UPDATE mcp_connectors" in query
    assert args == ("conn-1", "Renamed", False)


async def test_postgres_connector_delete_scopes_by_tenant():
    pool = _FakePool()

    await PostgresConnectorRepository(pool).delete(
        TenantId("acme"), ConnectorId("conn-1")
    )

    query, args = pool.calls[0]
    assert "DELETE FROM mcp_connectors" in query
    assert args == ("conn-1", "acme")
