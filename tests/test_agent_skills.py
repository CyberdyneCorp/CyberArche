"""Saved agent skills: variable expansion, scoping, permissions, router."""

from __future__ import annotations

import pytest

from cyberarche.domain.errors import NotAuthorized
from cyberarche.domain.memberships import Role, WorkspaceMembership
from cyberarche.domain.skills import expand, parse_variables

from tests.conftest import caller
from tests.test_agent import make_document


def test_parse_and_expand_variables():
    instr = "Summarize {doc} for {audience}. Keep {literal_untouched} as-is."
    variables = parse_variables(instr)
    assert variables == ["doc", "audience", "literal_untouched"]
    # Declared vars expand; a declared var with no value becomes empty.
    out = expand(instr, ["doc", "audience"], {"doc": "the plan", "audience": "execs"})
    assert out == "Summarize the plan for execs. Keep {literal_untouched} as-is."


async def test_save_parses_variables_and_lists(use_cases, alice):
    workspace, _ = await make_document(use_cases, alice)
    skill = await use_cases.skills.save(
        alice,
        workspace.id,
        name="Status update",
        instruction="Summarize this doc as a status update for {audience}.",
        description="Weekly status",
    )
    assert skill.variables == ["audience"]
    listed = await use_cases.skills.list(alice, workspace.id)
    assert [s.name for s in listed] == ["Status update"]


async def test_instantiate_expands_into_instruction(use_cases, alice):
    workspace, _ = await make_document(use_cases, alice)
    skill = await use_cases.skills.save(
        alice,
        workspace.id,
        name="S",
        instruction="Rewrite for {audience} in {tone} tone.",
    )
    instruction = await use_cases.skills.instantiate(
        alice, workspace.id, skill.id, {"audience": "developers", "tone": "formal"}
    )
    assert instruction == "Rewrite for developers in formal tone."


async def test_skills_are_workspace_and_tenant_scoped(use_cases, alice):
    workspace, _ = await make_document(use_cases, alice)
    await use_cases.skills.save(
        alice, workspace.id, name="Secret", instruction="do a thing"
    )
    other = caller("mallory", "globex")
    with pytest.raises(NotAuthorized):
        await use_cases.skills.list(other, workspace.id)


async def test_only_editor_creates_and_owner_or_author_deletes(
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
        await use_cases.skills.save(viewer, workspace.id, name="x", instruction="y")

    skill = await use_cases.skills.save(
        alice, workspace.id, name="mine", instruction="do it"
    )
    # A non-author, non-owner editor cannot delete someone else's skill.
    editor = caller("dave", "acme")
    await memberships.add_workspace_member(
        WorkspaceMembership(
            workspace_id=workspace.id, user_id=editor.user_id,
            role=Role.EDITOR, granted_at=clock.now(),
        )
    )
    with pytest.raises(NotAuthorized):
        await use_cases.skills.delete(editor, workspace.id, skill.id)
    # The author can.
    await use_cases.skills.delete(alice, workspace.id, skill.id)
    assert await use_cases.skills.list(alice, workspace.id) == []


# ---- HTTP router -----------------------------------------------------------


def _auth(token: str = "alice-token") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_skills_router_roundtrip_and_instantiate(api):
    ws = api.post(
        "/api/v1/workspaces", json={"name": "WS"}, headers=_auth()
    ).json()["id"]
    base = f"/api/v1/workspaces/{ws}/agent/skills"

    created = api.post(
        base,
        json={
            "name": "Status",
            "instruction": "Summarize for {audience}.",
            "description": "d",
        },
        headers=_auth(),
    )
    assert created.status_code == 201
    skill = created.json()
    assert skill["variables"] == ["audience"]

    listed = api.get(base, headers=_auth()).json()
    assert [s["name"] for s in listed] == ["Status"]

    out = api.post(
        f"{base}/{skill['id']}/instantiate",
        json={"values": {"audience": "execs"}},
        headers=_auth(),
    )
    assert out.json()["instruction"] == "Summarize for execs."

    assert api.delete(f"{base}/{skill['id']}", headers=_auth()).status_code == 204
    assert api.get(base, headers=_auth()).json() == []
