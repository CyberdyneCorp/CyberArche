"""Autonomous scheduled agent tasks (ai-agent spec).

A `ScheduledAgentTask` runs the agent in the background with no live user; it is
authorized by its stored `owner_id`/`tenant_id`, never the service identity. A
minimal 5-field cron evaluator computes the next run time deterministically from
an injected clock (so the scheduler needs no third-party dependency).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from cyberarche.domain.errors import ValidationFailed
from cyberarche.domain.ids import (
    AgentTaskRunId,
    DocumentId,
    ScheduledAgentTaskId,
    TenantId,
    UserId,
    WorkspaceId,
)


@dataclass(frozen=True, slots=True)
class ScheduledAgentTask:
    id: ScheduledAgentTaskId
    tenant_id: TenantId
    owner_id: UserId
    name: str
    instruction: str
    workspace_id: WorkspaceId
    schedule_cron: str
    created_at: datetime
    updated_at: datetime
    document_id: DocumentId | None = None
    enabled: bool = True
    next_run_at: datetime | None = None
    running: bool = False
    lease_until: datetime | None = None
    max_tool_rounds: int = 8
    max_wall_seconds: int = 120
    max_actions: int = 20


@dataclass(frozen=True, slots=True)
class AgentTaskRun:
    id: AgentTaskRunId
    tenant_id: TenantId
    task_id: ScheduledAgentTaskId
    owner_id: UserId
    trigger: str
    outcome: str
    started_at: datetime
    finished_at: datetime | None = None
    document_id: DocumentId | None = None
    detail: str = ""
    tools_used: list[str] = field(default_factory=list)


# ---- minimal cron -----------------------------------------------------------


def _field_values(field_expr: str, low: int, high: int) -> set[int]:
    values: set[int] = set()
    for part in field_expr.split(","):
        step = 1
        token = part
        if "/" in token:
            token, step_s = token.split("/", 1)
            step = int(step_s)
            if step <= 0:
                raise ValidationFailed(f"invalid cron step: {part!r}")
        if token == "*":
            start, end = low, high
        elif "-" in token:
            a, b = token.split("-", 1)
            start, end = int(a), int(b)
        else:
            start = end = int(token)
        if start < low or end > high or start > end:
            raise ValidationFailed(f"cron field out of range: {part!r}")
        values.update(range(start, end + 1, step))
    return values


def validate_cron(expr: str) -> None:
    """Raise ValidationFailed unless `expr` is a supported 5-field cron string."""
    parts = expr.split()
    if len(parts) != 5:
        raise ValidationFailed("cron must have 5 fields: min hour dom mon dow")
    bounds = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 6)]
    for part, (low, high) in zip(parts, bounds, strict=True):
        _field_values(part, low, high)


def next_cron_time(expr: str, after: datetime) -> datetime:
    """The first minute strictly after `after` matching the cron expression.

    Day-of-month and day-of-week are AND-matched (the common cron cases —
    weekday schedules and monthly schedules — use `*` for the other field, so
    AND is equivalent there)."""
    minute, hour, dom, mon, dow = expr.split()
    m = _field_values(minute, 0, 59)
    h = _field_values(hour, 0, 23)
    d = _field_values(dom, 1, 31)
    mo = _field_values(mon, 1, 12)
    w = _field_values(dow, 0, 6)  # cron: 0=Sunday..6=Saturday

    t = (after + timedelta(minutes=1)).replace(second=0, microsecond=0)
    for _ in range(366 * 24 * 60):
        if (
            t.minute in m
            and t.hour in h
            and t.month in mo
            and t.day in d
            and ((t.weekday() + 1) % 7) in w
        ):
            return t
        t += timedelta(minutes=1)
    raise ValidationFailed("cron expression has no run within a year")
