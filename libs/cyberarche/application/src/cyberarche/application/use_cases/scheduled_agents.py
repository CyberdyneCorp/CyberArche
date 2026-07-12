"""Autonomous scheduled agent use cases (autonomous-agents spec).

Users create scheduled tasks; a scheduler tick (`run_due`) claims each due task
with a lease and runs it through the agent's background path. A run is
authorized by the task's stored owner — a real user's authority executed by the
service — never by the service identity. Output lands in a document via the CRDT
and the owner is notified; every run is audited.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from cyberarche.application.authz import AccessControl
from cyberarche.application.kernel import CallerContext
from cyberarche.application.ports.notifications import NotificationRepository
from cyberarche.application.ports.scheduled_agents import ScheduledAgentRepository
from cyberarche.application.ports.telemetry import ClockPort, IdPort
from cyberarche.application.use_cases.agent import AgentUseCases
from cyberarche.application.use_cases.documents import DocumentUseCases
from cyberarche.domain.errors import NotAuthorized, NotFound, ValidationFailed
from cyberarche.domain.ids import (
    AgentTaskRunId,
    DocumentId,
    NotificationId,
    ScheduledAgentTaskId,
    UserId,
    WorkspaceId,
)
from cyberarche.domain.memberships import Role
from cyberarche.domain.notifications import Notification
from cyberarche.domain.scheduled_agents import (
    AgentTaskRun,
    ScheduledAgentTask,
    next_cron_time,
    validate_cron,
)

_LEASE_SECONDS = 300
_MAX_PER_TICK = 100


class ScheduledAgentUseCases:
    def __init__(
        self,
        tasks: ScheduledAgentRepository,
        agent: AgentUseCases,
        documents: DocumentUseCases,
        notifications: NotificationRepository,
        access: AccessControl,
        clock: ClockPort,
        ids: IdPort,
    ) -> None:
        self._tasks = tasks
        self._agent = agent
        self._documents = documents
        self._notifications = notifications
        self._access = access
        self._clock = clock
        self._ids = ids

    # ---- management --------------------------------------------------------

    async def create(
        self,
        caller: CallerContext,
        workspace_id: WorkspaceId,
        *,
        name: str,
        instruction: str,
        schedule_cron: str,
        document_id: DocumentId | None = None,
        max_tool_rounds: int = 8,
        max_wall_seconds: int = 120,
        max_actions: int = 20,
    ) -> ScheduledAgentTask:
        await self._access.require_workspace(caller, workspace_id, Role.EDITOR)
        name = name.strip()
        instruction = instruction.strip()
        if not name or not instruction:
            raise ValidationFailed("task name and instruction are required")
        validate_cron(schedule_cron)
        now = self._clock.now()
        task = ScheduledAgentTask(
            id=ScheduledAgentTaskId(self._ids.new_id()),
            tenant_id=caller.tenant_id,
            owner_id=caller.user_id,
            name=name,
            instruction=instruction,
            workspace_id=workspace_id,
            document_id=document_id,
            schedule_cron=schedule_cron,
            enabled=True,
            next_run_at=next_cron_time(schedule_cron, now),
            max_tool_rounds=max_tool_rounds,
            max_wall_seconds=max_wall_seconds,
            max_actions=max_actions,
            created_at=now,
            updated_at=now,
        )
        await self._tasks.add(task)
        return task

    async def list(
        self, caller: CallerContext, workspace_id: WorkspaceId
    ) -> list[ScheduledAgentTask]:
        await self._access.require_workspace(caller, workspace_id, Role.VIEWER)
        return await self._tasks.list_for_workspace(caller.tenant_id, workspace_id)

    async def set_enabled(
        self,
        caller: CallerContext,
        workspace_id: WorkspaceId,
        task_id: ScheduledAgentTaskId,
        enabled: bool,
    ) -> ScheduledAgentTask:
        await self._access.require_workspace(caller, workspace_id, Role.EDITOR)
        task = await self._require_task(caller, workspace_id, task_id)
        now = self._clock.now()
        updated = _replace(
            task,
            enabled=enabled,
            next_run_at=next_cron_time(task.schedule_cron, now)
            if enabled
            else task.next_run_at,
            updated_at=now,
        )
        await self._tasks.update(updated)
        return updated

    async def delete(
        self,
        caller: CallerContext,
        workspace_id: WorkspaceId,
        task_id: ScheduledAgentTaskId,
    ) -> None:
        task = await self._require_task(caller, workspace_id, task_id)
        role = await self._access.workspace_role(caller, workspace_id)
        if role != Role.OWNER and str(task.owner_id) != str(caller.user_id):
            raise NotAuthorized("only the owner or a workspace owner may delete")
        await self._tasks.delete(caller.tenant_id, task_id)

    async def list_runs(
        self,
        caller: CallerContext,
        workspace_id: WorkspaceId,
        task_id: ScheduledAgentTaskId,
    ) -> list[AgentTaskRun]:
        await self._require_task(caller, workspace_id, task_id)
        return await self._tasks.list_runs(caller.tenant_id, task_id)

    async def _require_task(
        self,
        caller: CallerContext,
        workspace_id: WorkspaceId,
        task_id: ScheduledAgentTaskId,
    ) -> ScheduledAgentTask:
        await self._access.require_workspace(caller, workspace_id, Role.VIEWER)
        task = await self._tasks.get(caller.tenant_id, task_id)
        if task is None or str(task.workspace_id) != str(workspace_id):
            raise NotFound("task not found")
        return task

    # ---- scheduling / execution -------------------------------------------

    async def run_due(self, now: datetime | None = None) -> int:
        """Claim and run every due task (one lease at a time). Returns the count
        executed. Called by the in-process scheduler tick."""
        now = now or self._clock.now()
        lease_until = now + timedelta(seconds=_LEASE_SECONDS)
        executed = 0
        while executed < _MAX_PER_TICK:
            task = await self._tasks.claim_due(now, lease_until)
            if task is None:
                break
            await self.execute_task(task, trigger="schedule")
            executed += 1
        return executed

    async def execute_task(self, task: ScheduledAgentTask, *, trigger: str) -> None:
        """Run one task as its owner, write output to a document, notify, audit,
        and release the lease with the next scheduled run."""
        owner = CallerContext(user_id=task.owner_id, tenant_id=task.tenant_id)
        started = self._clock.now()
        document_id = task.document_id
        outcome = "failed"
        detail = ""
        tools_used: list[str] = []
        try:
            if document_id is None:
                document = await self._documents.create(
                    owner,
                    workspace_id=task.workspace_id,
                    title=f"{task.name} — agent output",
                )
                document_id = document.id
            result = await self._agent.run_background(
                owner,
                document_id,
                instruction=task.instruction,
                max_tool_rounds=task.max_tool_rounds,
                max_actions=task.max_actions,
                max_wall_seconds=task.max_wall_seconds,
            )
            outcome = result.outcome
            detail = result.text[:500]
            tools_used = result.tools_used
            # Guarantee output lands in the document even if the agent only
            # answered (apply_blocks splits any markdown into typed blocks).
            if not result.edited and result.text.strip():
                await self._agent.apply_blocks(
                    owner,
                    document_id,
                    [{"type": "paragraph", "data": {"text": result.text}}],
                )
            await self._notify(task, document_id, outcome)
        except NotAuthorized:
            outcome, detail = "denied", "owner no longer has access"
        except Exception as error:  # a failed run must not break the scheduler
            outcome, detail = "failed", str(error)[:500]
        finally:
            await self._record_run(
                task, trigger, document_id, outcome, detail, tools_used, started
            )
            await self._tasks.release(
                task.id, next_run_at=next_cron_time(task.schedule_cron, started)
            )

    async def _notify(
        self,
        task: ScheduledAgentTask,
        document_id: DocumentId | None,
        outcome: str,
    ) -> None:
        await self._notifications.add(
            Notification(
                id=NotificationId(self._ids.new_id()),
                tenant_id=task.tenant_id,
                recipient_id=task.owner_id,
                kind="agent_task",
                actor_id=task.owner_id,
                document_id=document_id,
                comment_id=None,
                snippet=f"Agent task '{task.name}' {outcome}",
                created_at=self._clock.now(),
            )
        )

    async def _record_run(
        self,
        task: ScheduledAgentTask,
        trigger: str,
        document_id: DocumentId | None,
        outcome: str,
        detail: str,
        tools_used: list[str],
        started: datetime,
    ) -> None:
        await self._tasks.record_run(
            AgentTaskRun(
                id=AgentTaskRunId(self._ids.new_id()),
                tenant_id=task.tenant_id,
                task_id=task.id,
                owner_id=task.owner_id,
                trigger=trigger,
                document_id=document_id,
                outcome=outcome,
                detail=detail,
                tools_used=list(tools_used),
                started_at=started,
                finished_at=self._clock.now(),
            )
        )


def _replace(task: ScheduledAgentTask, **changes: object) -> ScheduledAgentTask:
    import dataclasses

    return dataclasses.replace(task, **changes)


# Re-export for callers that build a caller identity by id.
__all__ = ["ScheduledAgentUseCases", "CallerContext", "UserId"]
