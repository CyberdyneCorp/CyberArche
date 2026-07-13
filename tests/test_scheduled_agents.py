"""Autonomous scheduled agents: cron, owner-scoped background execution, safety
limits, locking, audit, and notification (autonomous-agents spec)."""

from __future__ import annotations

import dataclasses
import json
from datetime import UTC, datetime, timedelta

import pytest

from cyberarche.adapters.outbound.postgres.scheduled_agents import (
    PostgresScheduledAgentRepository,
)
from cyberarche.application.ports.llm import LLMResponse, ToolCall
from cyberarche.domain.errors import NotAuthorized, ValidationFailed
from cyberarche.domain.ids import (
    AgentTaskRunId,
    DocumentId,
    ScheduledAgentTaskId,
    TenantId,
    UserId,
    WorkspaceId,
)
from cyberarche.domain.memberships import Role, WorkspaceMembership
from cyberarche.domain.scheduled_agents import (
    AgentTaskRun,
    ScheduledAgentTask,
    next_cron_time,
    validate_cron,
)

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


# ---- Postgres adapter (stubbed pool) ----------------------------------------


class FakePool:
    """Records queries/args; returns pre-programmed rows (dicts stand in for
    asyncpg.Record, which is only read via ``row[key]``)."""

    def __init__(self, *, row=None, rows=()):
        self.row = row
        self.rows = list(rows)
        self.calls: list[tuple[str, tuple]] = []

    async def execute(self, query, *args):
        self.calls.append((query, args))

    async def fetchrow(self, query, *args):
        self.calls.append((query, args))
        return self.row

    async def fetch(self, query, *args):
        self.calls.append((query, args))
        return list(self.rows)


PG_NOW = datetime(2026, 7, 12, 9, 0, tzinfo=UTC)


def pg_task(**overrides) -> ScheduledAgentTask:
    fields = dict(
        id=ScheduledAgentTaskId("task-1"),
        tenant_id=TenantId("acme"),
        owner_id=UserId("alice"),
        name="Daily digest",
        instruction="Summarize recent changes.",
        workspace_id=WorkspaceId("ws-1"),
        schedule_cron="0 9 * * *",
        created_at=PG_NOW,
        updated_at=PG_NOW,
        document_id=DocumentId("doc-1"),
        enabled=True,
        next_run_at=PG_NOW,
        running=False,
        lease_until=None,
    )
    fields.update(overrides)
    return ScheduledAgentTask(**fields)


def pg_run(**overrides) -> AgentTaskRun:
    fields = dict(
        id=AgentTaskRunId("run-1"),
        tenant_id=TenantId("acme"),
        task_id=ScheduledAgentTaskId("task-1"),
        owner_id=UserId("alice"),
        trigger="schedule",
        outcome="succeeded",
        started_at=PG_NOW,
        finished_at=PG_NOW + timedelta(seconds=5),
        document_id=DocumentId("doc-1"),
        detail="ok",
        tools_used=["read_document", "apply_blocks"],
    )
    fields.update(overrides)
    return AgentTaskRun(**fields)


async def test_pg_add_binds_every_column_in_order():
    pool = FakePool()
    task = pg_task()
    await PostgresScheduledAgentRepository(pool).add(task)
    _, args = pool.calls[0]
    assert args == (
        task.id, task.tenant_id, task.owner_id, task.name, task.instruction,
        task.workspace_id, task.document_id, task.schedule_cron, task.enabled,
        task.next_run_at, task.running, task.lease_until, task.max_tool_rounds,
        task.max_wall_seconds, task.max_actions, task.created_at, task.updated_at,
    )


async def test_pg_get_round_trips_task_row():
    task = pg_task(lease_until=PG_NOW, running=True)
    pool = FakePool(row=dataclasses.asdict(task))
    repo = PostgresScheduledAgentRepository(pool)
    assert await repo.get(task.tenant_id, task.id) == task
    _, args = pool.calls[0]
    assert args == (task.tenant_id, task.id)


async def test_pg_get_returns_none_when_missing():
    repo = PostgresScheduledAgentRepository(FakePool(row=None))
    assert await repo.get(TenantId("acme"), ScheduledAgentTaskId("nope")) is None


async def test_pg_task_row_with_null_document_maps_to_none():
    task = pg_task(document_id=None)
    pool = FakePool(row=dataclasses.asdict(task))
    loaded = await PostgresScheduledAgentRepository(pool).get(task.tenant_id, task.id)
    assert loaded is not None and loaded.document_id is None


async def test_pg_list_for_workspace_maps_rows_and_scopes_query():
    a, b = pg_task(), pg_task(id=ScheduledAgentTaskId("task-2"), document_id=None)
    pool = FakePool(rows=[dataclasses.asdict(a), dataclasses.asdict(b)])
    repo = PostgresScheduledAgentRepository(pool)
    assert await repo.list_for_workspace(a.tenant_id, a.workspace_id) == [a, b]
    _, args = pool.calls[0]
    assert args == (a.tenant_id, a.workspace_id)


async def test_pg_update_binds_scope_then_mutable_fields():
    pool = FakePool()
    task = pg_task(enabled=False, next_run_at=None)
    await PostgresScheduledAgentRepository(pool).update(task)
    _, args = pool.calls[0]
    assert args == (
        task.tenant_id, task.id, task.name, task.instruction, task.document_id,
        task.schedule_cron, task.enabled, task.next_run_at, task.running,
        task.lease_until, task.max_tool_rounds, task.max_wall_seconds,
        task.max_actions, task.updated_at,
    )


async def test_pg_delete_is_tenant_scoped():
    pool = FakePool()
    await PostgresScheduledAgentRepository(pool).delete(
        TenantId("acme"), ScheduledAgentTaskId("task-1")
    )
    query, args = pool.calls[0]
    assert "DELETE FROM scheduled_agent_tasks" in query
    assert args == (TenantId("acme"), ScheduledAgentTaskId("task-1"))


async def test_pg_claim_due_returns_claimed_task():
    task = pg_task(running=True, lease_until=PG_NOW + timedelta(minutes=5))
    pool = FakePool(row=dataclasses.asdict(task))
    claimed = await PostgresScheduledAgentRepository(pool).claim_due(
        PG_NOW, PG_NOW + timedelta(minutes=5)
    )
    assert claimed == task
    _, args = pool.calls[0]
    assert args == (PG_NOW, PG_NOW + timedelta(minutes=5))


async def test_pg_claim_due_returns_none_when_nothing_due():
    pool = FakePool(row=None)
    assert (
        await PostgresScheduledAgentRepository(pool).claim_due(
            PG_NOW, PG_NOW + timedelta(minutes=5)
        )
        is None
    )


async def test_pg_release_binds_task_and_next_run():
    pool = FakePool()
    await PostgresScheduledAgentRepository(pool).release(
        ScheduledAgentTaskId("task-1"), next_run_at=PG_NOW
    )
    _, args = pool.calls[0]
    assert args == (ScheduledAgentTaskId("task-1"), PG_NOW)


async def test_pg_release_accepts_none_next_run():
    pool = FakePool()
    await PostgresScheduledAgentRepository(pool).release(
        ScheduledAgentTaskId("task-1"), next_run_at=None
    )
    _, args = pool.calls[0]
    assert args == (ScheduledAgentTaskId("task-1"), None)


async def test_pg_record_run_serializes_tools_as_json():
    pool = FakePool()
    run = pg_run()
    await PostgresScheduledAgentRepository(pool).record_run(run)
    _, args = pool.calls[0]
    assert args == (
        run.id, run.tenant_id, run.task_id, run.owner_id, run.trigger,
        run.document_id, run.outcome, run.detail,
        json.dumps(["read_document", "apply_blocks"]),
        run.started_at, run.finished_at,
    )


async def test_pg_list_runs_parses_jsonb_tools_string():
    run = pg_run()
    row = dataclasses.asdict(run) | {"tools_used": json.dumps(run.tools_used)}
    pool = FakePool(rows=[row])
    repo = PostgresScheduledAgentRepository(pool)
    assert await repo.list_runs(run.tenant_id, run.task_id) == [run]
    _, args = pool.calls[0]
    assert args == (run.tenant_id, run.task_id, 20)


async def test_pg_list_runs_maps_null_tools_and_document():
    run = pg_run(document_id=None, finished_at=None, tools_used=[])
    row = dataclasses.asdict(run) | {"tools_used": None}
    pool = FakePool(rows=[row])
    [loaded] = await PostgresScheduledAgentRepository(pool).list_runs(
        run.tenant_id, run.task_id
    )
    assert loaded == run
    assert loaded.tools_used == [] and loaded.document_id is None


async def test_pg_list_runs_clamps_negative_limit_to_zero():
    pool = FakePool(rows=[])
    await PostgresScheduledAgentRepository(pool).list_runs(
        TenantId("acme"), ScheduledAgentTaskId("task-1"), limit=-3
    )
    _, args = pool.calls[0]
    assert args[-1] == 0
