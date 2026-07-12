"""Autonomous scheduled agents: cron, owner-scoped background execution, safety
limits, locking, audit, and notification (autonomous-agents spec)."""

from __future__ import annotations

import dataclasses
from datetime import timedelta

import pytest

from cyberarche.application.ports.llm import LLMResponse, ToolCall
from cyberarche.domain.errors import NotAuthorized, ValidationFailed
from cyberarche.domain.memberships import Role, WorkspaceMembership
from cyberarche.domain.scheduled_agents import next_cron_time, validate_cron

from tests.conftest import caller
from tests.test_agent import make_document, seed_blocks


# ---- cron ------------------------------------------------------------------


def test_cron_validation_and_next_time():
    validate_cron("*/15 * * * *")
    with pytest.raises(ValidationFailed):
        validate_cron("bad")
    with pytest.raises(ValidationFailed):
        validate_cron("99 * * * *")
    from datetime import datetime

    base = datetime(2026, 7, 12, 9, 7)
    assert next_cron_time("*/15 * * * *", base) == datetime(2026, 7, 12, 9, 15)
    assert next_cron_time("0 0 * * *", base) == datetime(2026, 7, 13, 0, 0)


# ---- management ------------------------------------------------------------


async def test_create_stores_owner_tenant_and_next_run(use_cases, alice):
    workspace, document = await make_document(use_cases, alice)
    task = await use_cases.scheduled_agents.create(
        alice,
        workspace.id,
        name="Daily digest",
        instruction="Summarize recent changes.",
        schedule_cron="0 9 * * *",
        document_id=document.id,
    )
    assert task.owner_id == alice.user_id
    assert str(task.tenant_id) == str(alice.tenant_id)
    assert task.enabled and task.next_run_at is not None
    listed = await use_cases.scheduled_agents.list(alice, workspace.id)
    assert [t.id for t in listed] == [task.id]


async def test_create_rejects_bad_cron(use_cases, alice):
    workspace, _ = await make_document(use_cases, alice)
    with pytest.raises(ValidationFailed):
        await use_cases.scheduled_agents.create(
            alice, workspace.id, name="x", instruction="y", schedule_cron="nope"
        )


async def test_only_editor_creates(use_cases, memberships, clock, alice):
    workspace, _ = await make_document(use_cases, alice)
    viewer = caller("carol", "acme")
    await memberships.add_workspace_member(
        WorkspaceMembership(
            workspace_id=workspace.id, user_id=viewer.user_id,
            role=Role.VIEWER, granted_at=clock.now(),
        )
    )
    with pytest.raises(NotAuthorized):
        await use_cases.scheduled_agents.create(
            viewer, workspace.id, name="x", instruction="y", schedule_cron="* * * * *"
        )


# ---- execution -------------------------------------------------------------


def _make_due(scheduled_repo, task, clock):
    scheduled_repo._tasks[str(task.id)] = dataclasses.replace(
        task, next_run_at=clock.now() - timedelta(minutes=1)
    )


async def test_due_task_runs_writes_to_doc_and_notifies(
    use_cases, llm, scheduled_repo, clock, alice
):
    workspace, document = await make_document(use_cases, alice)
    task = await use_cases.scheduled_agents.create(
        alice, workspace.id, name="Digest",
        instruction="Write a one-line status.", schedule_cron="0 9 * * *",
        document_id=document.id,
    )
    _make_due(scheduled_repo, task, clock)
    # The agent just answers (no editing tool); execute_task appends the answer.
    llm._responses = [LLMResponse(text="All systems nominal.", model="m")]

    ran = await use_cases.scheduled_agents.run_due(clock.now())
    assert ran == 1

    # Result written into the target document.
    state = await use_cases.realtime.current_state(alice, document.id)
    texts = [
        b["data"].get("text", "")
        for b in use_cases.agent._engine.read_blocks(state)
    ]
    assert any("All systems nominal." in t for t in texts)
    # Owner notified.
    notes = await use_cases.notifications.list(alice)
    assert any(n.kind == "agent_task" for n in notes)
    # Audited.
    runs = await use_cases.scheduled_agents.list_runs(alice, workspace.id, task.id)
    assert len(runs) == 1 and runs[0].outcome == "succeeded"


async def test_disabled_task_does_not_run(use_cases, scheduled_repo, clock, alice):
    workspace, document = await make_document(use_cases, alice)
    task = await use_cases.scheduled_agents.create(
        alice, workspace.id, name="x", instruction="y", schedule_cron="0 9 * * *",
        document_id=document.id,
    )
    await use_cases.scheduled_agents.set_enabled(alice, workspace.id, task.id, False)
    _make_due(scheduled_repo, task, clock)  # due, but disabled
    # re-disable after making due (make_due reset the record)
    scheduled_repo._tasks[str(task.id)] = dataclasses.replace(
        scheduled_repo._tasks[str(task.id)], enabled=False
    )

    assert await use_cases.scheduled_agents.run_due(clock.now()) == 0
    assert await use_cases.scheduled_agents.list_runs(alice, workspace.id, task.id) == []


async def test_task_is_claimed_at_most_once_per_tick(
    use_cases, scheduled_repo, clock, alice
):
    workspace, document = await make_document(use_cases, alice)
    task = await use_cases.scheduled_agents.create(
        alice, workspace.id, name="x", instruction="y", schedule_cron="0 9 * * *",
        document_id=document.id,
    )
    _make_due(scheduled_repo, task, clock)
    now, lease = clock.now(), clock.now() + timedelta(seconds=300)
    first = await scheduled_repo.claim_due(now, lease)
    second = await scheduled_repo.claim_due(now, lease)
    assert first is not None and second is None  # losing claimant skips


async def test_background_run_refuses_destructive_tools(
    use_cases, llm, scheduled_repo, clock, alice
):
    workspace, document = await make_document(use_cases, alice)
    await seed_blocks(use_cases, alice, document.id, ["delete me"])
    task = await use_cases.scheduled_agents.create(
        alice, workspace.id, name="x", instruction="remove the block",
        schedule_cron="0 9 * * *", document_id=document.id,
    )
    _make_due(scheduled_repo, task, clock)
    llm._responses = [
        LLMResponse(
            text="",
            tool_calls=(
                ToolCall(id="c1", name="delete_block", arguments={"block_id": "b1"}),
            ),
        ),
        LLMResponse(text="done", model="m"),
    ]

    await use_cases.scheduled_agents.run_due(clock.now())

    # The block was NOT deleted.
    state = await use_cases.realtime.current_state(alice, document.id)
    ids = [b["id"] for b in use_cases.agent._engine.read_blocks(state)]
    assert "b1" in ids


async def test_run_denied_when_owner_lost_access(
    use_cases, scheduled_repo, clock, alice
):
    workspace, document = await make_document(use_cases, alice)
    task = await use_cases.scheduled_agents.create(
        alice, workspace.id, name="x", instruction="y", schedule_cron="0 9 * * *",
        document_id=document.id,
    )
    _make_due(scheduled_repo, task, clock)
    # Rewrite the task's owner to someone with no access to the document.
    scheduled_repo._tasks[str(task.id)] = dataclasses.replace(
        scheduled_repo._tasks[str(task.id)], owner_id=caller("nobody", "acme").user_id
    )

    await use_cases.scheduled_agents.run_due(clock.now())
    runs = await use_cases.scheduled_agents.list_runs(alice, workspace.id, task.id)
    assert len(runs) == 1 and runs[0].outcome == "denied"


async def test_run_stops_on_action_limit(
    use_cases, llm, scheduled_repo, clock, alice
):
    workspace, document = await make_document(use_cases, alice)
    task = await use_cases.scheduled_agents.create(
        alice, workspace.id, name="x", instruction="loop",
        schedule_cron="0 9 * * *", document_id=document.id,
        max_actions=1, max_tool_rounds=8,
    )
    _make_due(scheduled_repo, task, clock)
    # The model keeps wanting to insert blocks forever; the action cap stops it.
    insert = LLMResponse(
        text="",
        tool_calls=(
            ToolCall(id="c", name="insert_blocks",
                     arguments={"blocks": [{"type": "paragraph", "data": {"text": "x"}}]}),
        ),
    )
    llm._responses = [insert] * 10

    await use_cases.scheduled_agents.run_due(clock.now())
    runs = await use_cases.scheduled_agents.list_runs(alice, workspace.id, task.id)
    assert runs[0].outcome == "stopped_actions"


async def test_run_stops_on_round_limit(
    use_cases, llm, scheduled_repo, clock, alice
):
    workspace, document = await make_document(use_cases, alice)
    task = await use_cases.scheduled_agents.create(
        alice, workspace.id, name="x", instruction="loop",
        schedule_cron="0 9 * * *", document_id=document.id,
        max_tool_rounds=2, max_actions=99,
    )
    _make_due(scheduled_repo, task, clock)
    insert = LLMResponse(
        text="",
        tool_calls=(
            ToolCall(id="c", name="insert_blocks",
                     arguments={"blocks": [{"type": "paragraph", "data": {"text": "x"}}]}),
        ),
    )
    llm._responses = [insert] * 10

    await use_cases.scheduled_agents.run_due(clock.now())
    runs = await use_cases.scheduled_agents.list_runs(alice, workspace.id, task.id)
    assert runs[0].outcome == "stopped_rounds"


async def test_run_stops_on_wall_clock_limit(
    use_cases, llm, scheduled_repo, clock, alice
):
    workspace, document = await make_document(use_cases, alice)
    task = await use_cases.scheduled_agents.create(
        alice, workspace.id, name="x", instruction="loop",
        schedule_cron="0 9 * * *", document_id=document.id,
        max_wall_seconds=0,  # deadline == now → trips on the first round
    )
    _make_due(scheduled_repo, task, clock)
    insert = LLMResponse(
        text="",
        tool_calls=(
            ToolCall(id="c", name="insert_blocks",
                     arguments={"blocks": [{"type": "paragraph", "data": {"text": "x"}}]}),
        ),
    )
    llm._responses = [insert] * 10

    await use_cases.scheduled_agents.run_due(clock.now())
    runs = await use_cases.scheduled_agents.list_runs(alice, workspace.id, task.id)
    assert runs[0].outcome == "stopped_timeout"


# ---- HTTP router -----------------------------------------------------------


def _auth(token: str = "alice-token") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_scheduled_agents_router_crud(api):
    ws = api.post("/api/v1/workspaces", json={"name": "WS"}, headers=_auth()).json()["id"]
    base = f"/api/v1/workspaces/{ws}/agent/tasks"

    created = api.post(
        base,
        json={"name": "Daily", "instruction": "digest", "schedule_cron": "0 9 * * *"},
        headers=_auth(),
    )
    assert created.status_code == 201
    task = created.json()
    assert task["enabled"] and task["next_run_at"]

    assert [t["name"] for t in api.get(base, headers=_auth()).json()] == ["Daily"]

    disabled = api.patch(
        f"{base}/{task['id']}", json={"enabled": False}, headers=_auth()
    )
    assert disabled.json()["enabled"] is False

    assert api.get(f"{base}/{task['id']}/runs", headers=_auth()).json() == []
    assert api.delete(f"{base}/{task['id']}", headers=_auth()).status_code == 204


def test_scheduled_agents_router_rejects_bad_cron(api):
    ws = api.post("/api/v1/workspaces", json={"name": "WS"}, headers=_auth()).json()["id"]
    resp = api.post(
        f"/api/v1/workspaces/{ws}/agent/tasks",
        json={"name": "x", "instruction": "y", "schedule_cron": "not-cron"},
        headers=_auth(),
    )
    assert resp.status_code == 422
