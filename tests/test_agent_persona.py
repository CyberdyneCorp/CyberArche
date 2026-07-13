"""Agent persona + memory: custom instructions injection, memory recall,
permissions, tenant isolation, and the secret guard (ai-agent spec)."""

from __future__ import annotations

import pytest

from cyberarche.application.ports.llm import LLMResponse, ToolCall
from cyberarche.domain.errors import NotAuthorized, ValidationFailed
from cyberarche.domain.memberships import Role, WorkspaceMembership

from tests.conftest import caller
from tests.test_agent import make_document


async def test_workspace_instructions_are_injected_into_the_system_prompt(
    use_cases, llm, alice
):
    workspace, document = await make_document(use_cases, alice)
    await use_cases.persona.set_workspace_instructions(
        alice, workspace.id, "Always answer in Portuguese and cite sources."
    )
    llm._responses = [LLMResponse(text="Olá", model="m")]

    await use_cases.agent.ask(alice, document.id, instruction="hi")

    system = llm.requests[0][0]
    assert system.role == "system"
    assert "Always answer in Portuguese" in system.content


async def test_personal_instructions_layer_only_reaches_their_author(
    use_cases, llm, memberships, clock, alice
):
    workspace, document = await make_document(use_cases, alice)
    bob = caller("bob", "acme")
    await memberships.add_workspace_member(
        WorkspaceMembership(
            workspace_id=workspace.id, user_id=bob.user_id,
            role=Role.EDITOR, granted_at=clock.now(),
        )
    )
    await use_cases.persona.set_personal_instructions(
        alice, workspace.id, "Call me Captain."
    )
    llm._responses = [LLMResponse(text="ok", model="m")]

    await use_cases.agent.ask(alice, document.id, instruction="hi")
    assert "Call me Captain." in llm.requests[0][0].content

    # Bob, editing the same doc/workspace, does not see Alice's personal layer.
    llm.requests.clear()
    llm._responses = [LLMResponse(text="ok", model="m")]
    await use_cases.agent.ask(bob, document.id, instruction="hi")
    assert "Call me Captain." not in llm.requests[0][0].content


async def test_only_editors_set_workspace_instructions(
    use_cases, memberships, clock, alice
):
    workspace, _ = await make_document(use_cases, alice)
    viewer = caller("carol", "acme")
    await memberships.add_workspace_member(
        WorkspaceMembership(
            workspace_id=workspace.id, user_id=viewer.user_id,
            role=Role.VIEWER, granted_at=clock.now(),
        )
    )
    with pytest.raises(NotAuthorized):
        await use_cases.persona.set_workspace_instructions(
            viewer, workspace.id, "no can do"
        )


async def test_remember_tool_saves_and_a_later_run_recalls_it(
    use_cases, llm, alice
):
    workspace, document = await make_document(use_cases, alice)
    # Run 1: the agent saves a memory via the tool.
    llm._responses = [
        LLMResponse(
            text="",
            tool_calls=(
                ToolCall(
                    id="c1",
                    name="remember",
                    arguments={"note": "The team deploys on Coolify."},
                ),
            ),
        ),
        LLMResponse(text="Noted.", model="m"),
    ]
    await use_cases.agent.ask(alice, document.id, instruction="remember our stack")

    saved = await use_cases.persona.list_memories(alice, workspace.id)
    assert len(saved) == 1 and "Coolify" in saved[0].text

    # Run 2: the memory is injected into the next run's system prompt.
    llm.requests.clear()
    llm._responses = [LLMResponse(text="Coolify", model="m")]
    await use_cases.agent.ask(alice, document.id, instruction="where do we deploy?")
    assert "Coolify" in llm.requests[0][0].content


async def test_memory_is_tenant_and_workspace_scoped(use_cases, alice):
    workspace, _ = await make_document(use_cases, alice)
    await use_cases.persona.add_memory(alice, workspace.id, "acme secret sauce")

    # A caller in another tenant cannot see acme's memory even for the same id.
    other = caller("mallory", "globex")
    with pytest.raises(NotAuthorized):
        await use_cases.persona.list_memories(other, workspace.id)


async def test_deleted_memory_is_no_longer_injected(use_cases, llm, alice):
    workspace, document = await make_document(use_cases, alice)
    memory = await use_cases.persona.add_memory(
        alice, workspace.id, "Widgets ship on Fridays."
    )
    await use_cases.persona.delete_memory(alice, workspace.id, memory.id)

    llm._responses = [LLMResponse(text="ok", model="m")]
    await use_cases.agent.ask(alice, document.id, instruction="when do widgets ship?")
    assert "Widgets ship on Fridays" not in llm.requests[0][0].content


async def test_secret_looking_memory_is_rejected(use_cases, alice):
    workspace, _ = await make_document(use_cases, alice)
    with pytest.raises(ValidationFailed):
        await use_cases.persona.add_memory(
            alice, workspace.id, "the API key is sk-proj-ABCDEFGHIJKLMNOPQRSTUVWX"
        )
    # Nothing was stored.
    assert await use_cases.persona.list_memories(alice, workspace.id) == []


async def test_non_member_does_not_get_persona_injected(
    use_cases, llm, alice
):
    # build_context returns "" for a caller with no workspace role, so a private
    # doc shared directly never leaks the workspace's persona.
    workspace, document = await make_document(use_cases, alice)
    await use_cases.persona.set_workspace_instructions(
        alice, workspace.id, "secret house style"
    )
    context = await use_cases.persona.build_context(
        caller("stranger", "acme"), workspace.id, "hi"
    )
    assert context == ""


# ---- custom instructions CRUD -----------------------------------------------


async def test_workspace_instructions_roundtrip_and_clear(use_cases, alice):
    workspace, _ = await make_document(use_cases, alice)
    assert await use_cases.persona.get_workspace_instructions(alice, workspace.id) is None

    await use_cases.persona.set_workspace_instructions(alice, workspace.id, "Be brief.")
    assert (
        await use_cases.persona.get_workspace_instructions(alice, workspace.id)
        == "Be brief."
    )

    await use_cases.persona.clear_workspace_instructions(alice, workspace.id)
    assert await use_cases.persona.get_workspace_instructions(alice, workspace.id) is None


async def test_personal_instructions_roundtrip_and_clear(use_cases, alice):
    workspace, _ = await make_document(use_cases, alice)
    assert await use_cases.persona.get_personal_instructions(alice, workspace.id) is None

    await use_cases.persona.set_personal_instructions(alice, workspace.id, "Call me Al.")
    assert (
        await use_cases.persona.get_personal_instructions(alice, workspace.id)
        == "Call me Al."
    )

    await use_cases.persona.clear_personal_instructions(alice, workspace.id)
    assert await use_cases.persona.get_personal_instructions(alice, workspace.id) is None


async def test_viewer_may_set_their_own_personal_instructions(
    use_cases, memberships, clock, alice
):
    # A personal layer is private to its author: workspace membership suffices.
    workspace, _ = await make_document(use_cases, alice)
    viewer = caller("carol", "acme")
    await memberships.add_workspace_member(
        WorkspaceMembership(
            workspace_id=workspace.id, user_id=viewer.user_id,
            role=Role.VIEWER, granted_at=clock.now(),
        )
    )

    await use_cases.persona.set_personal_instructions(viewer, workspace.id, "mine")
    assert (
        await use_cases.persona.get_personal_instructions(viewer, workspace.id)
        == "mine"
    )


async def test_only_editors_clear_workspace_instructions(
    use_cases, memberships, clock, alice
):
    workspace, _ = await make_document(use_cases, alice)
    await use_cases.persona.set_workspace_instructions(alice, workspace.id, "keep")
    viewer = caller("carol", "acme")
    await memberships.add_workspace_member(
        WorkspaceMembership(
            workspace_id=workspace.id, user_id=viewer.user_id,
            role=Role.VIEWER, granted_at=clock.now(),
        )
    )
    with pytest.raises(NotAuthorized):
        await use_cases.persona.clear_workspace_instructions(viewer, workspace.id)


async def test_non_member_cannot_read_instructions(use_cases, alice):
    workspace, _ = await make_document(use_cases, alice)
    stranger = caller("stranger", "acme")
    with pytest.raises(NotAuthorized):
        await use_cases.persona.get_workspace_instructions(stranger, workspace.id)
    with pytest.raises(NotAuthorized):
        await use_cases.persona.get_personal_instructions(stranger, workspace.id)


async def test_setting_blank_instructions_clears_the_record(use_cases, alice):
    workspace, _ = await make_document(use_cases, alice)
    await use_cases.persona.set_workspace_instructions(alice, workspace.id, "old")

    await use_cases.persona.set_workspace_instructions(alice, workspace.id, "   ")

    assert await use_cases.persona.get_workspace_instructions(alice, workspace.id) is None


async def test_updating_instructions_keeps_the_record_id(use_cases, alice):
    workspace, _ = await make_document(use_cases, alice)
    await use_cases.persona.set_workspace_instructions(alice, workspace.id, "v1")
    first = await use_cases.persona._instructions.get(
        alice.tenant_id, workspace.id, None
    )

    await use_cases.persona.set_workspace_instructions(alice, workspace.id, "v2")
    second = await use_cases.persona._instructions.get(
        alice.tenant_id, workspace.id, None
    )

    assert second.id == first.id and second.instructions == "v2"


# ---- memory CRUD -------------------------------------------------------------


async def test_add_memory_rejects_blank_text(use_cases, alice):
    workspace, _ = await make_document(use_cases, alice)
    with pytest.raises(ValidationFailed):
        await use_cases.persona.add_memory(alice, workspace.id, "   ")


async def test_update_memory_replaces_text_and_keeps_provenance(
    use_cases, clock, alice
):
    workspace, _ = await make_document(use_cases, alice)
    memory = await use_cases.persona.add_memory(alice, workspace.id, "old fact")
    clock.tick()

    updated = await use_cases.persona.update_memory(
        alice, workspace.id, memory.id, "new fact"
    )

    assert updated.id == memory.id
    assert updated.text == "new fact"
    assert updated.created_by == memory.created_by
    assert updated.created_at == memory.created_at
    assert updated.updated_at > memory.updated_at
    listing = await use_cases.persona.list_memories(alice, workspace.id)
    assert [m.text for m in listing] == ["new fact"]


async def test_update_memory_rejects_blank_and_secret_text(use_cases, alice):
    workspace, _ = await make_document(use_cases, alice)
    memory = await use_cases.persona.add_memory(alice, workspace.id, "fine")

    with pytest.raises(ValidationFailed):
        await use_cases.persona.update_memory(alice, workspace.id, memory.id, "  ")
    with pytest.raises(ValidationFailed):
        await use_cases.persona.update_memory(
            alice, workspace.id, memory.id,
            "the API key is sk-proj-ABCDEFGHIJKLMNOPQRSTUVWX",
        )


async def test_update_unknown_memory_fails(use_cases, alice):
    from cyberarche.domain.ids import AgentMemoryId

    workspace, _ = await make_document(use_cases, alice)
    with pytest.raises(ValidationFailed):
        await use_cases.persona.update_memory(
            alice, workspace.id, AgentMemoryId("ghost"), "text"
        )


async def test_memory_cannot_be_reached_through_another_workspace(use_cases, alice):
    # The memory id must belong to the addressed workspace.
    workspace_a, _ = await make_document(use_cases, alice)
    workspace_b = await use_cases.workspaces.create(alice, name="Other")
    memory = await use_cases.persona.add_memory(alice, workspace_a.id, "a-fact")

    with pytest.raises(ValidationFailed):
        await use_cases.persona.update_memory(
            alice, workspace_b.id, memory.id, "hijack"
        )
    with pytest.raises(ValidationFailed):
        await use_cases.persona.delete_memory(alice, workspace_b.id, memory.id)


async def test_author_may_delete_their_own_memory_even_as_viewer(
    use_cases, memberships, clock, alice
):
    workspace, _ = await make_document(use_cases, alice)
    bob = caller("bob", "acme")
    await memberships.add_workspace_member(
        WorkspaceMembership(
            workspace_id=workspace.id, user_id=bob.user_id,
            role=Role.EDITOR, granted_at=clock.now(),
        )
    )
    memory = await use_cases.persona.add_memory(bob, workspace.id, "bob's note")
    # Bob is later downgraded to viewer; he may still delete his own memory.
    await memberships.add_workspace_member(
        WorkspaceMembership(
            workspace_id=workspace.id, user_id=bob.user_id,
            role=Role.VIEWER, granted_at=clock.now(),
        )
    )

    await use_cases.persona.delete_memory(bob, workspace.id, memory.id)
    assert await use_cases.persona.list_memories(alice, workspace.id) == []


async def test_viewer_cannot_delete_someone_elses_memory(
    use_cases, memberships, clock, alice
):
    workspace, _ = await make_document(use_cases, alice)
    memory = await use_cases.persona.add_memory(alice, workspace.id, "alice's note")
    viewer = caller("carol", "acme")
    await memberships.add_workspace_member(
        WorkspaceMembership(
            workspace_id=workspace.id, user_id=viewer.user_id,
            role=Role.VIEWER, granted_at=clock.now(),
        )
    )

    with pytest.raises(NotAuthorized):
        await use_cases.persona.delete_memory(viewer, workspace.id, memory.id)
    # Still there.
    listing = await use_cases.persona.list_memories(alice, workspace.id)
    assert [m.text for m in listing] == ["alice's note"]


async def test_viewer_cannot_add_memories(use_cases, memberships, clock, alice):
    workspace, _ = await make_document(use_cases, alice)
    viewer = caller("carol", "acme")
    await memberships.add_workspace_member(
        WorkspaceMembership(
            workspace_id=workspace.id, user_id=viewer.user_id,
            role=Role.VIEWER, granted_at=clock.now(),
        )
    )
    with pytest.raises(NotAuthorized):
        await use_cases.persona.add_memory(viewer, workspace.id, "sneaky")


# ---- injection budget (D-4) ---------------------------------------------------


async def test_build_context_is_empty_without_persona_data(use_cases, alice):
    workspace, _ = await make_document(use_cases, alice)
    assert await use_cases.persona.build_context(alice, workspace.id, "hi") == ""


async def test_build_context_clips_long_workspace_instructions(use_cases, alice):
    workspace, _ = await make_document(use_cases, alice)
    await use_cases.persona.set_workspace_instructions(
        alice, workspace.id, "style " * 1000  # ~6000 chars, over the 4000 budget
    )

    context = await use_cases.persona.build_context(alice, workspace.id, "hi")

    assert "## Workspace instructions" in context
    assert "…" in context  # clipped, not dumped wholesale
    body = context.split("follow these)\n", 1)[1]
    assert len(body) <= 4000


async def test_build_context_includes_personal_layer_header(use_cases, alice):
    workspace, _ = await make_document(use_cases, alice)
    await use_cases.persona.set_personal_instructions(
        alice, workspace.id, "Address me as Captain."
    )

    context = await use_cases.persona.build_context(alice, workspace.id, "hi")

    assert "## The current user's personal instructions" in context
    assert "Address me as Captain." in context


async def test_memory_over_the_char_budget_is_not_injected(use_cases, alice):
    workspace, _ = await make_document(use_cases, alice)
    await use_cases.persona.add_memory(alice, workspace.id, "important word " * 200)

    context = await use_cases.persona.build_context(alice, workspace.id, "hi")

    # The only memory blows the 2000-char budget → no memory section at all.
    assert "Remembered facts" not in context
    assert context == ""


async def test_memories_within_budget_are_listed_newest_first(
    use_cases, clock, alice
):
    workspace, _ = await make_document(use_cases, alice)
    await use_cases.persona.add_memory(alice, workspace.id, "first fact")
    clock.tick()
    await use_cases.persona.add_memory(alice, workspace.id, "second fact")

    context = await use_cases.persona.build_context(alice, workspace.id, "hello")

    assert "## Remembered facts about this workspace" in context
    assert context.index("second fact") < context.index("first fact")


# ---- HTTP router -----------------------------------------------------------


def _auth(token: str = "alice-token") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_persona_router_instructions_and_memories_roundtrip(api):
    ws = api.post(
        "/api/v1/workspaces", json={"name": "WS"}, headers=_auth()
    ).json()["id"]
    base = f"/api/v1/workspaces/{ws}/agent"

    assert api.put(
        f"{base}/instructions",
        json={"scope": "workspace", "text": "Be concise."},
        headers=_auth(),
    ).status_code == 204
    got = api.get(f"{base}/instructions", headers=_auth()).json()
    assert got["workspace"] == "Be concise." and got["personal"] is None

    created = api.post(
        f"{base}/memories", json={"text": "We use pytest."}, headers=_auth()
    )
    assert created.status_code == 201
    memory_id = created.json()["id"]
    listing = api.get(f"{base}/memories", headers=_auth()).json()
    assert [m["text"] for m in listing] == ["We use pytest."]

    assert api.delete(
        f"{base}/memories/{memory_id}", headers=_auth()
    ).status_code == 204
    assert api.get(f"{base}/memories", headers=_auth()).json() == []


def test_persona_router_rejects_a_secret_memory(api):
    ws = api.post(
        "/api/v1/workspaces", json={"name": "WS"}, headers=_auth()
    ).json()["id"]
    resp = api.post(
        f"/api/v1/workspaces/{ws}/agent/memories",
        json={"text": "token=ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"},
        headers=_auth(),
    )
    assert resp.status_code == 422


def test_persona_router_denies_a_non_member(api):
    ws = api.post(
        "/api/v1/workspaces", json={"name": "WS"}, headers=_auth()
    ).json()["id"]
    # Mallory (tenant globex) has no role on Alice's acme workspace.
    resp = api.put(
        f"/api/v1/workspaces/{ws}/agent/instructions",
        json={"scope": "workspace", "text": "mine now"},
        headers=_auth("mallory-token"),
    )
    assert resp.status_code == 403
