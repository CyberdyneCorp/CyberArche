"""ScheduledAgentRepository over Postgres, with lease-based single-claim."""

from __future__ import annotations

import json
from datetime import datetime

import asyncpg

from cyberarche.domain.ids import (
    AgentTaskRunId,
    DocumentId,
    ScheduledAgentTaskId,
    TenantId,
    UserId,
    WorkspaceId,
)
from cyberarche.domain.scheduled_agents import AgentTaskRun, ScheduledAgentTask


def _task(row: asyncpg.Record) -> ScheduledAgentTask:
    return ScheduledAgentTask(
        id=ScheduledAgentTaskId(row["id"]),
        tenant_id=TenantId(row["tenant_id"]),
        owner_id=UserId(row["owner_id"]),
        name=row["name"],
        instruction=row["instruction"],
        workspace_id=WorkspaceId(row["workspace_id"]),
        document_id=DocumentId(row["document_id"]) if row["document_id"] else None,
        schedule_cron=row["schedule_cron"],
        enabled=row["enabled"],
        next_run_at=row["next_run_at"],
        running=row["running"],
        lease_until=row["lease_until"],
        max_tool_rounds=row["max_tool_rounds"],
        max_wall_seconds=row["max_wall_seconds"],
        max_actions=row["max_actions"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _run(row: asyncpg.Record) -> AgentTaskRun:
    tools = row["tools_used"]
    if isinstance(tools, str):
        tools = json.loads(tools)
    return AgentTaskRun(
        id=AgentTaskRunId(row["id"]),
        tenant_id=TenantId(row["tenant_id"]),
        task_id=ScheduledAgentTaskId(row["task_id"]),
        owner_id=UserId(row["owner_id"]),
        trigger=row["trigger"],
        document_id=DocumentId(row["document_id"]) if row["document_id"] else None,
        outcome=row["outcome"],
        detail=row["detail"],
        tools_used=list(tools or []),
        started_at=row["started_at"],
        finished_at=row["finished_at"],
    )


class PostgresScheduledAgentRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def add(self, task: ScheduledAgentTask) -> None:
        await self._pool.execute(
            """
            INSERT INTO scheduled_agent_tasks
                (id, tenant_id, owner_id, name, instruction, workspace_id,
                 document_id, schedule_cron, enabled, next_run_at, running,
                 lease_until, max_tool_rounds, max_wall_seconds, max_actions,
                 created_at, updated_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17)
            """,
            task.id, task.tenant_id, task.owner_id, task.name, task.instruction,
            task.workspace_id, task.document_id, task.schedule_cron, task.enabled,
            task.next_run_at, task.running, task.lease_until, task.max_tool_rounds,
            task.max_wall_seconds, task.max_actions, task.created_at, task.updated_at,
        )

    async def get(
        self, tenant_id: TenantId, task_id: ScheduledAgentTaskId
    ) -> ScheduledAgentTask | None:
        row = await self._pool.fetchrow(
            "SELECT * FROM scheduled_agent_tasks WHERE tenant_id = $1 AND id = $2",
            tenant_id,
            task_id,
        )
        return _task(row) if row else None

    async def list_for_workspace(
        self, tenant_id: TenantId, workspace_id: WorkspaceId
    ) -> list[ScheduledAgentTask]:
        rows = await self._pool.fetch(
            """
            SELECT * FROM scheduled_agent_tasks
            WHERE tenant_id = $1 AND workspace_id = $2
            ORDER BY created_at DESC
            """,
            tenant_id,
            workspace_id,
        )
        return [_task(r) for r in rows]

    async def update(self, task: ScheduledAgentTask) -> None:
        await self._pool.execute(
            """
            UPDATE scheduled_agent_tasks SET
                name=$3, instruction=$4, document_id=$5, schedule_cron=$6,
                enabled=$7, next_run_at=$8, running=$9, lease_until=$10,
                max_tool_rounds=$11, max_wall_seconds=$12, max_actions=$13,
                updated_at=$14
            WHERE tenant_id = $1 AND id = $2
            """,
            task.tenant_id, task.id, task.name, task.instruction, task.document_id,
            task.schedule_cron, task.enabled, task.next_run_at, task.running,
            task.lease_until, task.max_tool_rounds, task.max_wall_seconds,
            task.max_actions, task.updated_at,
        )

    async def delete(
        self, tenant_id: TenantId, task_id: ScheduledAgentTaskId
    ) -> None:
        await self._pool.execute(
            "DELETE FROM scheduled_agent_tasks WHERE tenant_id = $1 AND id = $2",
            tenant_id,
            task_id,
        )

    async def claim_due(
        self, now: datetime, lease_until: datetime
    ) -> ScheduledAgentTask | None:
        # Atomic claim: lock one due, unleased row and mark it running. SKIP
        # LOCKED lets concurrent schedulers grab different rows; a task is thus
        # executed at most once per tick.
        row = await self._pool.fetchrow(
            """
            UPDATE scheduled_agent_tasks SET running = TRUE, lease_until = $2
            WHERE id = (
                SELECT id FROM scheduled_agent_tasks
                WHERE enabled = TRUE AND next_run_at IS NOT NULL
                  AND next_run_at <= $1
                  AND (running = FALSE OR lease_until < $1)
                ORDER BY next_run_at
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            RETURNING *
            """,
            now,
            lease_until,
        )
        return _task(row) if row else None

    async def release(
        self,
        task_id: ScheduledAgentTaskId,
        *,
        next_run_at: datetime | None,
    ) -> None:
        await self._pool.execute(
            """
            UPDATE scheduled_agent_tasks
            SET running = FALSE, lease_until = NULL, next_run_at = $2
            WHERE id = $1
            """,
            task_id,
            next_run_at,
        )

    async def record_run(self, run: AgentTaskRun) -> None:
        await self._pool.execute(
            """
            INSERT INTO agent_task_runs
                (id, tenant_id, task_id, owner_id, trigger, document_id,
                 outcome, detail, tools_used, started_at, finished_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb,$10,$11)
            """,
            run.id, run.tenant_id, run.task_id, run.owner_id, run.trigger,
            run.document_id, run.outcome, run.detail, json.dumps(run.tools_used),
            run.started_at, run.finished_at,
        )

    async def list_runs(
        self,
        tenant_id: TenantId,
        task_id: ScheduledAgentTaskId,
        *,
        limit: int = 20,
    ) -> list[AgentTaskRun]:
        rows = await self._pool.fetch(
            """
            SELECT * FROM agent_task_runs
            WHERE tenant_id = $1 AND task_id = $2
            ORDER BY started_at DESC
            LIMIT $3
            """,
            tenant_id,
            task_id,
            max(0, limit),
        )
        return [_run(r) for r in rows]
