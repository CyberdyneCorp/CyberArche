"""Saved agent skills: variable expansion, scoping, permissions, router."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from cyberarche.adapters.outbound.postgres.skills import PostgresAgentSkillRepository
from cyberarche.domain.errors import NotAuthorized, NotFound, ValidationFailed
from cyberarche.domain.ids import AgentSkillId, TenantId, UserId, WorkspaceId
from cyberarche.domain.memberships import Role, WorkspaceMembership
from cyberarche.domain.skills import AgentSkill, expand, parse_variables

from tests.conftest import caller
from tests.test_agent import make_document
from tests.test_teamspaces import FakePool


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


# ---- use-case branches -----------------------------------------------------


async def test_save_requires_name_and_instruction(use_cases, alice):
    workspace, _ = await make_document(use_cases, alice)
    with pytest.raises(ValidationFailed):
        await use_cases.skills.save(alice, workspace.id, name="  ", instruction="x")
    with pytest.raises(ValidationFailed):
        await use_cases.skills.save(alice, workspace.id, name="x", instruction="  ")


async def test_save_strips_whitespace(use_cases, alice):
    workspace, _ = await make_document(use_cases, alice)
    skill = await use_cases.skills.save(
        alice, workspace.id, name="  Status  ", instruction="  do it  ",
        description="  desc  ",
    )
    assert skill.name == "Status"
    assert skill.instruction == "do it"
    assert skill.description == "desc"


async def test_update_reparses_variables_and_preserves_authorship(use_cases, alice):
    workspace, _ = await make_document(use_cases, alice)
    original = await use_cases.skills.save(
        alice, workspace.id, name="S", instruction="Old {a}.", description="old"
    )
    updated = await use_cases.skills.update(
        alice,
        workspace.id,
        original.id,
        name="S2",
        instruction="New {b} and {c}.",
        description="new",
    )
    assert updated.id == original.id
    assert updated.name == "S2"
    assert updated.description == "new"
    assert updated.variables == ["b", "c"]
    assert updated.created_by == original.created_by
    assert updated.created_at == original.created_at
    listed = await use_cases.skills.list(alice, workspace.id)
    assert [s.name for s in listed] == ["S2"]


async def test_update_requires_name_and_instruction(use_cases, alice):
    workspace, _ = await make_document(use_cases, alice)
    skill = await use_cases.skills.save(
        alice, workspace.id, name="S", instruction="do it"
    )
    with pytest.raises(ValidationFailed):
        await use_cases.skills.update(
            alice, workspace.id, skill.id, name="", instruction="x"
        )
    with pytest.raises(ValidationFailed):
        await use_cases.skills.update(
            alice, workspace.id, skill.id, name="x", instruction=" "
        )


async def test_update_requires_editor(use_cases, memberships, clock, alice):
    workspace, _ = await make_document(use_cases, alice)
    skill = await use_cases.skills.save(
        alice, workspace.id, name="S", instruction="do it"
    )
    viewer = caller("carol", "acme")
    await memberships.add_workspace_member(
        WorkspaceMembership(
            workspace_id=workspace.id, user_id=viewer.user_id,
            role=Role.VIEWER, granted_at=clock.now(),
        )
    )
    with pytest.raises(NotAuthorized):
        await use_cases.skills.update(
            viewer, workspace.id, skill.id, name="x", instruction="y"
        )


async def test_missing_skill_is_not_found(use_cases, alice):
    workspace, _ = await make_document(use_cases, alice)
    missing = AgentSkillId("missing")
    with pytest.raises(NotFound):
        await use_cases.skills.update(
            alice, workspace.id, missing, name="x", instruction="y"
        )
    with pytest.raises(NotFound):
        await use_cases.skills.delete(alice, workspace.id, missing)
    with pytest.raises(NotFound):
        await use_cases.skills.instantiate(alice, workspace.id, missing, {})


async def test_skill_is_invisible_from_another_workspace(use_cases, alice):
    workspace, _ = await make_document(use_cases, alice)
    other = await use_cases.workspaces.create(alice, name="Other")
    skill = await use_cases.skills.save(
        alice, workspace.id, name="S", instruction="do it"
    )
    with pytest.raises(NotFound):
        await use_cases.skills.instantiate(alice, other.id, skill.id, {})
    with pytest.raises(NotFound):
        await use_cases.skills.update(
            alice, other.id, skill.id, name="x", instruction="y"
        )


async def test_owner_deletes_another_authors_skill(
    use_cases, memberships, clock, alice
):
    workspace, _ = await make_document(use_cases, alice)
    editor = caller("dave", "acme")
    await memberships.add_workspace_member(
        WorkspaceMembership(
            workspace_id=workspace.id, user_id=editor.user_id,
            role=Role.EDITOR, granted_at=clock.now(),
        )
    )
    skill = await use_cases.skills.save(
        editor, workspace.id, name="daves", instruction="do it"
    )
    # Alice authored nothing here, but as workspace owner she may delete.
    await use_cases.skills.delete(alice, workspace.id, skill.id)
    assert await use_cases.skills.list(alice, workspace.id) == []


async def test_instantiate_with_no_values_blanks_declared_variables(use_cases, alice):
    workspace, _ = await make_document(use_cases, alice)
    skill = await use_cases.skills.save(
        alice, workspace.id, name="S", instruction="Rewrite for {audience}."
    )
    assert (
        await use_cases.skills.instantiate(alice, workspace.id, skill.id, {})
        == "Rewrite for ."
    )


# --- Postgres adapter (fake pool: records queries, replays canned rows) -----

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _skill_row(**overrides: object) -> dict:
    row = {
        "id": "sk-1",
        "tenant_id": "acme",
        "workspace_id": "ws-1",
        "name": "Status update",
        "description": "Weekly status",
        "instruction": "Summarize for {audience}.",
        "variables": ["audience"],
        "created_by": "alice",
        "created_at": NOW,
    }
    row.update(overrides)
    return row


def _skill() -> AgentSkill:
    return AgentSkill(
        id=AgentSkillId("sk-1"),
        tenant_id=TenantId("acme"),
        workspace_id=WorkspaceId("ws-1"),
        name="Status update",
        description="Weekly status",
        instruction="Summarize for {audience}.",
        variables=["audience"],
        created_by=UserId("alice"),
        created_at=NOW,
    )


async def test_pg_skill_add_inserts_all_columns_with_json_variables():
    pool = FakePool()
    await PostgresAgentSkillRepository(pool).add(_skill())

    query, args = pool.calls[0]
    assert query.startswith("INSERT INTO agent_skills")
    assert args == (
        "sk-1",
        "acme",
        "ws-1",
        "Status update",
        "Weekly status",
        "Summarize for {audience}.",
        json.dumps(["audience"]),
        "alice",
        NOW,
    )


async def test_pg_skill_get_maps_row():
    pool = FakePool()
    pool.row = _skill_row()
    found = await PostgresAgentSkillRepository(pool).get(
        TenantId("acme"), AgentSkillId("sk-1")
    )

    assert found == _skill()
    assert pool.calls[0][1] == ("acme", "sk-1")


async def test_pg_skill_get_returns_none_when_missing():
    pool = FakePool()
    found = await PostgresAgentSkillRepository(pool).get(
        TenantId("acme"), AgentSkillId("nope")
    )
    assert found is None


async def test_pg_skill_get_decodes_jsonb_variables_string():
    # asyncpg returns jsonb as a JSON string unless a codec is registered.
    pool = FakePool()
    pool.row = _skill_row(variables='["audience", "tone"]')
    found = await PostgresAgentSkillRepository(pool).get(
        TenantId("acme"), AgentSkillId("sk-1")
    )
    assert found.variables == ["audience", "tone"]


async def test_pg_skill_row_with_null_variables_maps_to_empty_list():
    pool = FakePool()
    pool.row = _skill_row(variables=None)
    found = await PostgresAgentSkillRepository(pool).get(
        TenantId("acme"), AgentSkillId("sk-1")
    )
    assert found.variables == []


async def test_pg_skill_list_for_workspace_maps_rows():
    pool = FakePool()
    pool.rows = [_skill_row(), _skill_row(id="sk-2", name="Digest", variables=[])]
    listed = await PostgresAgentSkillRepository(pool).list_for_workspace(
        TenantId("acme"), WorkspaceId("ws-1")
    )

    assert [(s.id, s.name) for s in listed] == [
        ("sk-1", "Status update"),
        ("sk-2", "Digest"),
    ]
    assert listed[1].variables == []
    assert pool.calls[0][1] == ("acme", "ws-1")


async def test_pg_skill_update_writes_editable_fields():
    pool = FakePool()
    skill = _skill()
    await PostgresAgentSkillRepository(pool).update(skill)

    query, args = pool.calls[0]
    assert query.startswith("UPDATE agent_skills")
    assert args == (
        "acme",
        "sk-1",
        "Status update",
        "Weekly status",
        "Summarize for {audience}.",
        json.dumps(["audience"]),
    )


async def test_pg_skill_delete_scopes_by_tenant():
    pool = FakePool()
    await PostgresAgentSkillRepository(pool).delete(
        TenantId("acme"), AgentSkillId("sk-1")
    )

    query, args = pool.calls[0]
    assert query.startswith("DELETE FROM agent_skills")
    assert args == ("acme", "sk-1")
