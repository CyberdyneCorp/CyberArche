"""Redis adapters: regression tests for the worker-killing dequeue bug.

The live adapters are exercised against a real Redis when TEST_REDIS_URL is
set; the always-on tests use a fake client reproducing redis-py's behavior
(a blocking BRPOP surfaces its deadline as TimeoutError, not nil).
"""

from __future__ import annotations

import os

import pytest
from redis.exceptions import TimeoutError as RedisTimeoutError

from cyberarche.adapters.outbound.redis_infra.queue import RedisTaskQueue
from cyberarche.application.jobs import JobRunner


class TimingOutRedis:
    """redis-py raises TimeoutError from brpop when its socket read deadline
    coincides with the blocking timeout (observed with timeout=5.0)."""

    async def brpop(self, keys, timeout):  # noqa: ANN001
        raise RedisTimeoutError(f"Timeout reading from redis (timeout={timeout})")


class ExplodingRedis:
    async def brpop(self, keys, timeout):  # noqa: ANN001
        raise ConnectionError("broker went away")


async def test_idle_poll_returns_none_instead_of_raising():
    """Regression: a 5s idle BRPOP raised TimeoutError, which propagated out
    of run_forever and crash-looped the workers container."""
    queue = RedisTaskQueue(TimingOutRedis())

    assert await queue.dequeue(timeout=5.0) is None


async def test_run_once_on_idle_queue_reports_no_work():
    runner = JobRunner(RedisTaskQueue(TimingOutRedis()))

    assert await runner.run_once(timeout=5.0) is False


async def test_run_forever_survives_a_broker_failure(monkeypatch):
    """A transient broker error must be logged and retried, never fatal."""
    import cyberarche.application.jobs as jobs

    monkeypatch.setattr(jobs, "_RETRY_BACKOFF_SECONDS", 0.0)
    runner = JobRunner(RedisTaskQueue(ExplodingRedis()))

    calls = {"n": 0}
    original = runner.run_once

    async def counting_run_once(**kwargs):
        calls["n"] += 1
        if calls["n"] >= 3:
            raise KeyboardInterrupt  # break out of the service loop
        return await original(**kwargs)

    runner.run_once = counting_run_once  # type: ignore[method-assign]
    with pytest.raises(KeyboardInterrupt):
        await runner.run_forever(timeout=0.01)
    assert calls["n"] == 3  # kept looping through the broker errors


@pytest.mark.skipif(
    not os.environ.get("TEST_REDIS_URL"), reason="TEST_REDIS_URL not configured"
)
async def test_live_redis_queue_and_bus_roundtrip():
    import asyncio

    import redis.asyncio as aioredis

    from cyberarche.adapters.outbound.redis_infra.bus import RedisPeerBus

    client = aioredis.from_url(os.environ["TEST_REDIS_URL"])
    try:
        queue = RedisTaskQueue(client, key="cyberarche:test:jobs")
        job_id = await queue.enqueue("demo.job", {"n": 1})
        job = await queue.dequeue(timeout=2.0)
        assert job is not None and job.id == job_id and job.payload == {"n": 1}
        # The idle poll that used to kill the worker.
        assert await queue.dequeue(timeout=5.0) is None

        bus = RedisPeerBus(client)
        received: list[bytes] = []

        async def handler(message: bytes) -> None:
            received.append(message)

        unsubscribe = await bus.subscribe("cyberarche:test:doc", handler)
        await asyncio.sleep(0.3)
        await bus.publish("cyberarche:test:doc", b"\x00update")
        await asyncio.sleep(0.4)
        assert received == [b"\x00update"]

        await unsubscribe()
        await bus.publish("cyberarche:test:doc", b"\x00after")
        await asyncio.sleep(0.3)
        assert received == [b"\x00update"]  # no delivery after unsubscribe
    finally:
        await client.aclose()
