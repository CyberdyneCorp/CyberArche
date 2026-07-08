"""PeerBusPort adapter over Redis pub/sub.

One background reader task per subscribed channel dispatches incoming
messages to the local handler; unsubscribe cancels the reader.
"""

from __future__ import annotations

import asyncio
import contextlib

import redis.asyncio as aioredis

from cyberarche.application.ports.bus import MessageHandler, Unsubscribe


class RedisPeerBus:
    def __init__(self, client: aioredis.Redis) -> None:
        self._redis = client

    async def publish(self, channel: str, message: bytes) -> None:
        await self._redis.publish(channel, message)

    async def subscribe(
        self, channel: str, handler: MessageHandler
    ) -> Unsubscribe:
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(channel)

        async def reader() -> None:
            async for entry in pubsub.listen():
                if entry.get("type") != "message":
                    continue
                data = entry["data"]
                if isinstance(data, str):
                    data = data.encode()
                await handler(data)

        task = asyncio.create_task(reader())

        async def unsubscribe() -> None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

        return unsubscribe
