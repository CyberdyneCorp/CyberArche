"""architecture-quality 12.4/12.5: stateless replicas + broker-backed relay."""

from __future__ import annotations

import anyio
import pytest
from fastapi.testclient import TestClient

from cyberarche.adapters.inbound.http.realtime import (
    FRAME_CONTROL,
    FRAME_UPDATE,
    DocumentPeers,
)
from cyberarche.adapters.wiring import WiringConfig, build_container
from cyberarche.api.bootstrap import create_app
from cyberarche.api.config import Settings
from cyberarche.application.testing.fakes import InProcessPeerBus, StaticTokenPort
from cyberarche.domain.ids import DocumentId
from tests.conftest import TOKENS


def auth(token: str = "alice-token") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def replicas():
    """Two API replicas sharing one container (shared store + peer bus)."""

    async def build():
        return await build_container(
            WiringConfig(backend="memory"), token_port=StaticTokenPort(dict(TOKENS))
        )

    container = anyio.run(build)
    settings = Settings(backend="memory", auth_base_url="", rag_base_url="")
    app_one = create_app(settings, container=container)
    app_two = create_app(settings, container=container)
    with TestClient(app_one) as one, TestClient(app_two) as two:
        yield one, two


def test_any_replica_serves_any_request_without_sticky_sessions(replicas):
    one, two = replicas

    workspace = one.post(
        "/api/v1/workspaces", json={"name": "Shared"}, headers=auth()
    ).json()
    document = two.post(
        "/api/v1/documents",
        json={"workspace_id": workspace["id"], "title": "From replica two"},
        headers=auth(),
    ).json()

    # Reads on either replica see writes made on the other.
    assert one.get(f"/api/v1/documents/{document['id']}", headers=auth()).json()[
        "title"
    ] == "From replica two"
    assert [w["id"] for w in two.get("/api/v1/workspaces", headers=auth()).json()] == [
        workspace["id"]
    ]


class RecordingSocket:
    """Stands in for a WebSocket on a relay instance."""

    def __init__(self) -> None:
        self.frames: list[bytes] = []
        self.texts: list[str] = []

    async def send_bytes(self, data: bytes) -> None:
        self.frames.append(data)

    async def send_text(self, data: str) -> None:
        self.texts.append(data)


async def test_frames_cross_relay_instances_via_the_bus():
    """An edit published on instance A reaches sockets on instance B,
    and the origin socket never receives its own frame."""
    bus = InProcessPeerBus()
    instance_a, instance_b = DocumentPeers(bus), DocumentPeers(bus)
    doc = DocumentId("doc-1")

    sender, local_peer = RecordingSocket(), RecordingSocket()
    remote_peer = RecordingSocket()
    sender_id = await instance_a.join(doc, sender)
    await instance_a.join(doc, local_peer)
    await instance_b.join(doc, remote_peer)

    frame = bytes([FRAME_UPDATE]) + b"crdt-update"
    await instance_a.publish(doc, sender_id, frame)

    assert local_peer.frames == [frame]  # same instance
    assert remote_peer.frames == [frame]  # other instance, via the bus
    assert sender.frames == []  # origin excluded

    # Control frames arrive as text on every instance.
    await instance_a.publish(doc, sender_id, bytes([FRAME_CONTROL]) + b'{"x":1}')
    assert remote_peer.texts == ['{"x":1}']

    # Last local leave unsubscribes the instance from the channel.
    await instance_b.leave(doc, remote_peer)
    await instance_a.publish(doc, sender_id, frame)
    assert remote_peer.frames == [frame]  # nothing new after leaving


async def test_unknown_frame_types_are_ignored_by_delivery():
    bus = InProcessPeerBus()
    peers = DocumentPeers(bus)
    doc = DocumentId("doc-2")
    socket = RecordingSocket()
    sender_id = await peers.join(doc, socket)

    await peers.publish(doc, b"\x00" * 16, b"")  # empty frame: dropped
    await peers.publish(doc, sender_id, bytes([FRAME_UPDATE]) + b"u")  # own: skipped

    assert socket.frames == []
