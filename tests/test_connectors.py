"""external-mcp-connectors spec: registration, secrets, namespacing, opt-in."""

from __future__ import annotations

import pytest

from cyberarche.application.ports.llm import LLMResponse, ToolCall
from cyberarche.application.ports.mcp import ExternalTool
from cyberarche.application.use_cases import UseCases
from cyberarche.domain.errors import Conflict, NotFound, ValidationFailed

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