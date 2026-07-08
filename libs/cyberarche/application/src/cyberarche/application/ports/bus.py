"""Peer bus port (architecture-quality spec 12.5).

Realtime relay instances share live frames through this bus, so editors
connected to different replicas still see each other's edits immediately.
Frames are opaque envelopes; the relay owns their encoding.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol

Unsubscribe = Callable[[], Awaitable[None]]
MessageHandler = Callable[[bytes], Awaitable[None]]


class PeerBusPort(Protocol):
    async def publish(self, channel: str, message: bytes) -> None: ...

    async def subscribe(
        self, channel: str, handler: MessageHandler
    ) -> Unsubscribe:
        """Register a handler for a channel; returns an unsubscribe callable.
        Delivery includes messages published by this same subscriber —
        callers filter their own frames via the envelope."""
        ...
