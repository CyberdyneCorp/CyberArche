"""Worker job runner: consumes the task queue and dispatches to handlers.

Runs inside the workers deployable, built on the same composition root as
the API (architecture-quality spec). Handlers re-check permissions with
the reconstructed caller — a queued job grants nothing by itself.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from cyberarche.application.kernel import CallerContext
from cyberarche.application.ports.queue import QueuedJob, TaskQueuePort
from cyberarche.application.ports.storage import BlobStoragePort
from cyberarche.application.use_cases.knowledge import INGEST_JOB, KnowledgeUseCases
from cyberarche.domain.errors import NotFound
from cyberarche.domain.ids import TenantId, UserId, WorkspaceId

logger = logging.getLogger(__name__)

_RETRY_BACKOFF_SECONDS = 2.0

JobHandler = Callable[[dict], Awaitable[None]]


class JobRunner:
    def __init__(self, queue: TaskQueuePort) -> None:
        self._queue = queue
        self._handlers: dict[str, JobHandler] = {}

    def register(self, job_type: str, handler: JobHandler) -> None:
        self._handlers[job_type] = handler

    async def run_once(self, *, timeout: float = 1.0) -> bool:
        """Process at most one job; returns whether one was processed."""
        job = await self._queue.dequeue(timeout=timeout)
        if job is None:
            return False
        await self._dispatch(job)
        return True

    async def run_forever(self, *, timeout: float = 5.0) -> None:
        """Service loop: a transient queue/broker failure must never kill the
        worker — log, back off briefly, and keep consuming."""
        while True:
            try:
                await self.run_once(timeout=timeout)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("worker loop error; retrying")
                await asyncio.sleep(_RETRY_BACKOFF_SECONDS)

    async def _dispatch(self, job: QueuedJob) -> None:
        handler = self._handlers.get(job.type)
        if handler is None:
            logger.error("no handler for job type %s (job %s)", job.type, job.id)
            return
        try:
            await handler(job.payload)
        except Exception:  # keep the worker alive; the job is logged as failed
            logger.exception("job %s (%s) failed", job.id, job.type)


def caller_from_payload(payload: dict) -> CallerContext:
    caller = payload["caller"]
    return CallerContext(
        user_id=UserId(caller["user_id"]), tenant_id=TenantId(caller["tenant_id"])
    )


def register_knowledge_jobs(
    runner: JobRunner, knowledge: KnowledgeUseCases, blobs: BlobStoragePort
) -> None:
    async def ingest_file(payload: dict) -> None:
        blob = await blobs.get(payload["blob_key"])
        if blob is None:
            raise NotFound(f"blob missing for job: {payload['blob_key']}")
        await knowledge.ingest_file(
            caller_from_payload(payload),
            WorkspaceId(payload["workspace_id"]),
            filename=payload["filename"],
            content=blob.content,
            content_type=payload.get("content_type", blob.content_type),
            force=bool(payload.get("force", False)),
        )

    runner.register(INGEST_JOB, ingest_file)
