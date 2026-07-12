"""Scheduled-agent repository port (ai-agent spec). Tenant-isolated.

`claim_due` atomically leases one due task so a task runs at most once per tick
even under concurrent schedulers; `release` clears the lease and advances the
next run; run records provide the audit trail.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from cyberarche.domain.ids import (
    ScheduledAgentTaskId,
    TenantId,
    WorkspaceId,
)
from cyberarche.domain.scheduled_agents import AgentTaskRun, ScheduledAgentTask


class ScheduledAgentRepository(Protocol):
    async def add(self, task: ScheduledAgentTask) -> None: ...

    async def get(
        self, tenant_id: TenantId, task_id: ScheduledAgentTaskId
    ) -> ScheduledAgentTask | None: ...

    async def list_for_workspace(
        self, tenant_id: TenantId, workspace_id: WorkspaceId
    ) -> list[ScheduledAgentTask]:
        """The workspace's tasks, newest first."""
        ...

    async def update(self, task: ScheduledAgentTask) -> None:
        """Persist mutable fields (name/instruction/schedule/enabled/limits and
        scheduling state: next_run_at/running/lease_until)."""
        ...

    async def delete(
        self, tenant_id: TenantId, task_id: ScheduledAgentTaskId
    ) -> None: ...

    async def claim_due(
        self, now: datetime, lease_until: datetime
    ) -> ScheduledAgentTask | None:
        """Atomically claim ONE enabled task that is due (`next_run_at <= now`)
        and not currently leased (or whose lease has expired), marking it
        `running` with `lease_until`. Returns the claimed task, or None when no
        task is due. Tenant-agnostic: the scheduler runs across tenants."""
        ...

    async def release(
        self,
        task_id: ScheduledAgentTaskId,
        *,
        next_run_at: datetime | None,
    ) -> None:
        """Clear the lease and set the next scheduled run."""
        ...

    async def record_run(self, run: AgentTaskRun) -> None: ...

    async def list_runs(
        self, tenant_id: TenantId, task_id: ScheduledAgentTaskId, *, limit: int = 20
    ) -> list[AgentTaskRun]:
        """A task's recent run history, newest first."""
        ...
