"""Task queue port (architecture-quality spec 12.6).

Long-running or bulk work (file ingestion, large agent runs) is enqueued
and executed by horizontally scalable workers — never in request handlers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class QueuedJob:
    id: str
    type: str
    payload: dict[str, Any]


class TaskQueuePort(Protocol):
    async def enqueue(self, job_type: str, payload: dict[str, Any]) -> str:
        """Push a job; returns its id. Must be fast and non-blocking."""
        ...

    async def dequeue(self, *, timeout: float = 5.0) -> QueuedJob | None:
        """Pop the next job, waiting up to `timeout`; None on timeout."""
        ...
