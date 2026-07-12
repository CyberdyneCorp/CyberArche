"""Scheduled agent endpoints (autonomous-agents spec): CRUD over autonomous
tasks and their run history."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from cyberarche.adapters.inbound.http.dependencies import Caller, Cases
from cyberarche.domain.ids import DocumentId, ScheduledAgentTaskId, WorkspaceId
from cyberarche.domain.scheduled_agents import AgentTaskRun, ScheduledAgentTask

router = APIRouter(tags=["scheduled-agents"])


class TaskResponse(BaseModel):
    id: str
    name: str
    instruction: str
    schedule_cron: str
    document_id: str | None
    enabled: bool
    next_run_at: datetime | None
    owner_id: str
    max_tool_rounds: int
    max_wall_seconds: int
    max_actions: int

    @staticmethod
    def from_domain(t: ScheduledAgentTask) -> "TaskResponse":
        return TaskResponse(
            id=t.id,
            name=t.name,
            instruction=t.instruction,
            schedule_cron=t.schedule_cron,
            document_id=t.document_id,
            enabled=t.enabled,
            next_run_at=t.next_run_at,
            owner_id=t.owner_id,
            max_tool_rounds=t.max_tool_rounds,
            max_wall_seconds=t.max_wall_seconds,
            max_actions=t.max_actions,
        )


class RunResponse(BaseModel):
    id: str
    trigger: str
    outcome: str
    document_id: str | None
    detail: str
    started_at: datetime
    finished_at: datetime | None

    @staticmethod
    def from_domain(r: AgentTaskRun) -> "RunResponse":
        return RunResponse(
            id=r.id,
            trigger=r.trigger,
            outcome=r.outcome,
            document_id=r.document_id,
            detail=r.detail,
            started_at=r.started_at,
            finished_at=r.finished_at,
        )


class CreateTaskRequest(BaseModel):
    name: str
    instruction: str
    schedule_cron: str
    document_id: str | None = None
    max_tool_rounds: int = 8
    max_wall_seconds: int = 120
    max_actions: int = 20


class EnabledRequest(BaseModel):
    enabled: bool


_BASE = "/api/v1/workspaces/{workspace_id}/agent/tasks"


@router.get(_BASE)
async def list_tasks(
    workspace_id: str, cases: Cases, caller: Caller
) -> list[TaskResponse]:
    tasks = await cases.scheduled_agents.list(caller, WorkspaceId(workspace_id))
    return [TaskResponse.from_domain(t) for t in tasks]


@router.post(_BASE, status_code=201)
async def create_task(
    workspace_id: str, body: CreateTaskRequest, cases: Cases, caller: Caller
) -> TaskResponse:
    task = await cases.scheduled_agents.create(
        caller,
        WorkspaceId(workspace_id),
        name=body.name,
        instruction=body.instruction,
        schedule_cron=body.schedule_cron,
        document_id=DocumentId(body.document_id) if body.document_id else None,
        max_tool_rounds=body.max_tool_rounds,
        max_wall_seconds=body.max_wall_seconds,
        max_actions=body.max_actions,
    )
    return TaskResponse.from_domain(task)


@router.patch(f"{_BASE}/{{task_id}}")
async def set_enabled(
    workspace_id: str,
    task_id: str,
    body: EnabledRequest,
    cases: Cases,
    caller: Caller,
) -> TaskResponse:
    task = await cases.scheduled_agents.set_enabled(
        caller, WorkspaceId(workspace_id), ScheduledAgentTaskId(task_id), body.enabled
    )
    return TaskResponse.from_domain(task)


@router.delete(f"{_BASE}/{{task_id}}", status_code=204)
async def delete_task(
    workspace_id: str, task_id: str, cases: Cases, caller: Caller
) -> None:
    await cases.scheduled_agents.delete(
        caller, WorkspaceId(workspace_id), ScheduledAgentTaskId(task_id)
    )


@router.get(f"{_BASE}/{{task_id}}/runs")
async def list_runs(
    workspace_id: str, task_id: str, cases: Cases, caller: Caller
) -> list[RunResponse]:
    runs = await cases.scheduled_agents.list_runs(
        caller, WorkspaceId(workspace_id), ScheduledAgentTaskId(task_id)
    )
    return [RunResponse.from_domain(r) for r in runs]
