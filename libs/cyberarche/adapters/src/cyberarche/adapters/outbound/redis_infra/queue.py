"""TaskQueuePort adapter over a Redis list (LPUSH / BRPOP)."""

from __future__ import annotations

import json
import uuid

import redis.asyncio as aioredis
from redis.exceptions import TimeoutError as RedisTimeoutError

from cyberarche.application.ports.queue import QueuedJob

_KEY = "cyberarche:jobs"


class RedisTaskQueue:
    def __init__(self, client: aioredis.Redis, *, key: str = _KEY) -> None:
        self._redis = client
        self._key = key

    async def enqueue(self, job_type: str, payload: dict) -> str:
        job_id = uuid.uuid4().hex
        await self._redis.lpush(
            self._key, json.dumps({"id": job_id, "type": job_type, "payload": payload})
        )
        return job_id

    async def dequeue(self, *, timeout: float = 5.0) -> QueuedJob | None:
        """An idle poll returns None — never raises. redis-py surfaces the
        blocking read as a TimeoutError when its socket deadline coincides
        with BRPOP's timeout; that is 'no job', not a failure (a worker loop
        must not die on an idle queue)."""
        try:
            entry = await self._redis.brpop([self._key], timeout=timeout)
        except RedisTimeoutError:
            return None
        if entry is None:
            return None
        _, raw = entry
        data = json.loads(raw)
        return QueuedJob(id=data["id"], type=data["type"], payload=data["payload"])
