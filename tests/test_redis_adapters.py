"""Redis adapters: regression tests for the worker-killing dequeue bug.

The live adapters are exercised against a real Redis when TEST_REDIS_URL is
set; the always-on tests use a fake client reproducing redis-py's behavior
(a blocking BRPOP surfaces its deadline as TimeoutError, not nil).
"""

from __future__ import annotations

import asyncio
import os

import pytest
from redis.exceptions import TimeoutError as RedisTimeoutError

from cyberarche.adapters.outbound.redis_infra.bus import RedisPeerBus
from cyberarche.adapters.outbound.redis_infra.queue import RedisTaskQueue
from cyberarche.application.jobs import JobRunner
from cyberarche.application.ports.bus import MessageHandler


class FakeListRedis:
    """In-memory stand-in for the LPUSH/BRPOP pair used by RedisTaskQueue.
    BRPOP returns (key, raw) like redis-py, or None when the list is empty."""

    def __init__(self) -> None:
        self.lists: dict[str, list[bytes]] = {}

    async def lpush(self, key, value):  # noqa: ANN001
        self.lists.setdefault(key, []).insert(0, value.encode())

    async def brpop(self, keys, timeout):  # noqa: ANN001
        for key in keys:
            entries = self.lists.get(key)
            if entries:
                return key, entries.pop()
        return None


class TimingOutRedis:
    """redis-py raises TimeoutError from brpop when its socket read deadline
    coincides with the blocking timeout (observed with timeout=5.0)."""

    async def brpop(self, keys, timeout):  # noqa: ANN001
        raise RedisTimeoutError(f"Timeout reading from redis (timeout={timeout})")


class ExplodingRedis:
    async def brpop(self, keys, timeout):  # noqa: ANN001
        raise ConnectionError("broker went away")


async def test_enqueue_then_dequeue_roundtrips_the_job():
    queue = RedisTaskQueue(FakeListRedis())

    job_id = await queue.enqueue("demo.job", {"n": 1})
    job = await queue.dequeue(timeout=0.1)

    assert job is not None
    assert job.id == job_id
    assert job.type == "demo.job"
    assert job.payload == {"n": 1}


async def test_enqueue_returns_unique_ids_and_dequeues_fifo():
    queue = RedisTaskQueue(FakeListRedis())

    first_id = await queue.enqueue("demo.job", {"seq": 1})
    second_id = await queue.enqueue("demo.job", {"seq": 2})
    assert first_id != second_id

    first = await queue.dequeue(timeout=0.1)
    second = await queue.dequeue(timeout=0.1)
    assert first is not None and first.id == first_id
    assert second is not None and second.id == second_id


async def test_enqueue_writes_json_to_the_configured_key():
    client = FakeListRedis()
    queue = RedisTaskQueue(client, key="cyberarche:custom:jobs")

    await queue.enqueue("demo.job", {"n": 1})

    assert list(client.lists) == ["cyberarche:custom:jobs"]
    # The default key must stay untouched when a custom key is configured.
    assert await RedisTaskQueue(client).dequeue(timeout=0.1) is None
    assert (await RedisTaskQueue(client, key="cyberarche:custom:jobs").dequeue(timeout=0.1)) is not None


async def test_dequeue_on_empty_list_returns_none():
    """redis-py also reports 'no job' as a nil BRPOP reply on fast timeouts."""
    queue = RedisTaskQueue(FakeListRedis())

    assert await queue.dequeue(timeout=0.1) is None


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


class FakePubSub:
    """In-memory stand-in for redis-py's PubSub: listen() yields the raw
    entry dicts redis-py produces (subscribe confirmations and messages)."""

    def __init__(self, owner: "FakePubSubRedis") -> None:
        self._owner = owner
        self._entries: "asyncio.Queue[dict]" = asyncio.Queue()
        self.subscribed: list[str] = []
        self.unsubscribed: list[str] = []
        self.closed = False

    async def subscribe(self, channel):  # noqa: ANN001
        self.subscribed.append(channel)
        self._owner.pubsubs.setdefault(channel, []).append(self)
        self._entries.put_nowait(
            {"type": "subscribe", "channel": channel, "data": 1}
        )

    async def unsubscribe(self, channel):  # noqa: ANN001
        self.unsubscribed.append(channel)
        self._owner.pubsubs.get(channel, [self]).remove(self)

    async def aclose(self):
        self.closed = True

    def deliver(self, entry: dict) -> None:
        self._entries.put_nowait(entry)

    async def listen(self):
        while True:
            yield await self._entries.get()


class FakePubSubRedis:
    """In-memory stand-in for the publish/pubsub pair used by RedisPeerBus."""

    def __init__(self) -> None:
        self.pubsubs: dict[str, list[FakePubSub]] = {}
        self.published: list[tuple[str, object]] = []

    def pubsub(self) -> FakePubSub:
        return FakePubSub(self)

    async def publish(self, channel, message):  # noqa: ANN001
        self.published.append((channel, message))
        for pubsub in self.pubsubs.get(channel, []):
            pubsub.deliver(
                {"type": "message", "channel": channel, "data": message}
            )


def _collecting_handler() -> tuple[list[bytes], "MessageHandler"]:
    received: list[bytes] = []
    delivered = asyncio.Event()

    async def handler(message: bytes) -> None:
        received.append(message)
        delivered.set()

    handler.delivered = delivered  # type: ignore[attr-defined]
    return received, handler


async def test_bus_publish_delegates_to_redis_publish():
    client = FakePubSubRedis()
    bus = RedisPeerBus(client)

    await bus.publish("doc:1", b"\x00update")

    assert client.published == [("doc:1", b"\x00update")]


async def test_bus_subscribe_delivers_published_bytes_to_handler():
    client = FakePubSubRedis()
    bus = RedisPeerBus(client)
    received, handler = _collecting_handler()

    unsubscribe = await bus.subscribe("doc:1", handler)
    await bus.publish("doc:1", b"\x00update")
    await asyncio.wait_for(handler.delivered.wait(), timeout=1.0)

    assert received == [b"\x00update"]
    await unsubscribe()


async def test_bus_reader_skips_non_message_entries():
    """The subscribe-confirmation entry redis-py emits must never reach the
    handler; only entries with type == 'message' do."""
    client = FakePubSubRedis()
    bus = RedisPeerBus(client)
    received, handler = _collecting_handler()

    unsubscribe = await bus.subscribe("doc:1", handler)
    pubsub = client.pubsubs["doc:1"][0]
    pubsub.deliver({"channel": "doc:1", "data": b"typeless"})  # no "type" key
    await bus.publish("doc:1", b"real")
    await asyncio.wait_for(handler.delivered.wait(), timeout=1.0)

    assert received == [b"real"]
    await unsubscribe()


async def test_bus_encodes_str_payloads_to_bytes():
    """decode_responses clients hand back str; the handler contract is bytes."""
    client = FakePubSubRedis()
    bus = RedisPeerBus(client)
    received, handler = _collecting_handler()

    unsubscribe = await bus.subscribe("doc:1", handler)
    await bus.publish("doc:1", "texto")
    await asyncio.wait_for(handler.delivered.wait(), timeout=1.0)

    assert received == [b"texto"]
    await unsubscribe()


async def test_bus_delivers_multiple_messages_in_order():
    client = FakePubSubRedis()
    bus = RedisPeerBus(client)
    received: list[bytes] = []
    done = asyncio.Event()

    async def handler(message: bytes) -> None:
        received.append(message)
        if len(received) == 3:
            done.set()

    unsubscribe = await bus.subscribe("doc:1", handler)
    for payload in (b"a", b"b", b"c"):
        await bus.publish("doc:1", payload)
    await asyncio.wait_for(done.wait(), timeout=1.0)

    assert received == [b"a", b"b", b"c"]
    await unsubscribe()


async def test_bus_subscribe_registers_the_channel():
    client = FakePubSubRedis()
    bus = RedisPeerBus(client)
    received, handler = _collecting_handler()

    unsubscribe = await bus.subscribe("doc:42", handler)

    pubsub = client.pubsubs["doc:42"][0]
    assert pubsub.subscribed == ["doc:42"]
    await unsubscribe()


async def test_bus_unsubscribe_stops_delivery_and_closes_pubsub():
    client = FakePubSubRedis()
    bus = RedisPeerBus(client)
    received, handler = _collecting_handler()

    unsubscribe = await bus.subscribe("doc:1", handler)
    pubsub = client.pubsubs["doc:1"][0]
    await bus.publish("doc:1", b"before")
    await asyncio.wait_for(handler.delivered.wait(), timeout=1.0)

    await unsubscribe()

    assert pubsub.unsubscribed == ["doc:1"]
    assert pubsub.closed is True
    await bus.publish("doc:1", b"after")
    await asyncio.sleep(0.05)
    assert received == [b"before"]  # no delivery after unsubscribe


async def test_bus_unsubscribe_cancels_the_reader_task():
    """unsubscribe must swallow the reader's CancelledError, not raise it."""
    client = FakePubSubRedis()
    bus = RedisPeerBus(client)
    received, handler = _collecting_handler()

    before = len(asyncio.all_tasks())
    unsubscribe = await bus.subscribe("doc:1", handler)
    assert len(asyncio.all_tasks()) == before + 1  # reader task running

    await unsubscribe()  # must not raise CancelledError

    await asyncio.sleep(0)
    assert len(asyncio.all_tasks()) == before


async def test_bus_independent_subscriptions_per_channel():
    client = FakePubSubRedis()
    bus = RedisPeerBus(client)
    received_a, handler_a = _collecting_handler()
    received_b, handler_b = _collecting_handler()

    unsub_a = await bus.subscribe("doc:a", handler_a)
    unsub_b = await bus.subscribe("doc:b", handler_b)
    await bus.publish("doc:a", b"for-a")
    await asyncio.wait_for(handler_a.delivered.wait(), timeout=1.0)
    await asyncio.sleep(0.05)

    assert received_a == [b"for-a"]
    assert received_b == []
    await unsub_a()
    await unsub_b()


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
