"""WebSocket relay for CRDT sync and presence (realtime-collaboration spec).

Wire protocol (kept deliberately minimal; the web client adapts y-websocket
to it in the frontend task group):

- binary frame, first byte 0x00: CRDT update (persisted + broadcast)
- binary frame, first byte 0x01: awareness/presence (broadcast only)
- text frame: JSON control messages from the server (errors, presence_left)

Join: `WS /api/v1/documents/{id}/sync?token=<bearer>`. The server verifies
the token, authorizes VIEWER, and sends the current document state as one
0x00 frame. Every inbound update re-checks EDITOR through the use case, so
a viewer's update is rejected and never broadcast.

Fanout goes through the PeerBusPort (architecture-quality spec 12.5):
frames are published to a per-document channel and every relay instance
subscribed to that channel delivers to its local sockets — so editors on
different replicas see each other live. The envelope is a 16-byte origin
socket id followed by the frame; the origin socket is skipped on delivery.
The relay holds no document state; documents reconstruct from the
persisted update log (stateless service rule).
"""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from cyberarche.application.kernel import CallerContext
from cyberarche.application.ports.bus import PeerBusPort, Unsubscribe
from cyberarche.application.use_cases.realtime import updates_channel
from cyberarche.domain.errors import (
    NotAuthenticated,
    NotAuthorized,
    NotFound,
)
from cyberarche.domain.ids import DocumentId, TenantId, UserId

FRAME_UPDATE = 0x00
FRAME_AWARENESS = 0x01
FRAME_CONTROL = 0x02  # UTF-8 JSON payload, delivered as a text frame

_SOCKET_ID_BYTES = 16

router = APIRouter()


def _channel(document_id: DocumentId) -> str:
    return f"cyberarche:doc:{document_id}"


class DocumentPeers:
    """Per-instance socket registry bridged to the shared peer bus."""

    def __init__(self, bus: PeerBusPort) -> None:
        self._bus = bus
        self._sockets: dict[DocumentId, dict[WebSocket, bytes]] = {}
        self._unsubscribers: dict[DocumentId, tuple[Unsubscribe, ...]] = {}

    async def join(self, document_id: DocumentId, socket: WebSocket) -> bytes:
        socket_id = uuid.uuid4().bytes
        is_first_local = document_id not in self._sockets
        self._sockets.setdefault(document_id, {})[socket] = socket_id
        if is_first_local:
            # Socket-originated frames (awareness, control) between peers...
            peer_unsub = await self._bus.subscribe(
                _channel(document_id), self._deliverer(document_id)
            )
            # ...and RAW persisted updates from ANY inbound surface (WS,
            # HTTP agent, MCP), published by the realtime use case.
            update_unsub = await self._bus.subscribe(
                updates_channel(document_id), self._update_deliverer(document_id)
            )
            self._unsubscribers[document_id] = (peer_unsub, update_unsub)
        return socket_id

    async def leave(self, document_id: DocumentId, socket: WebSocket) -> None:
        sockets = self._sockets.get(document_id, {})
        sockets.pop(socket, None)
        if not sockets and document_id in self._sockets:
            del self._sockets[document_id]
            for unsubscribe in self._unsubscribers.pop(document_id, ()):
                await unsubscribe()

    async def publish(
        self, document_id: DocumentId, origin_socket_id: bytes, frame: bytes
    ) -> None:
        await self._bus.publish(_channel(document_id), origin_socket_id + frame)

    def _deliverer(self, document_id: DocumentId):
        async def deliver(message: bytes) -> None:
            origin, frame = message[:_SOCKET_ID_BYTES], message[_SOCKET_ID_BYTES:]
            if not frame:
                return
            for socket, socket_id in list(self._sockets.get(document_id, {}).items()):
                if socket_id == origin:
                    continue
                try:
                    if frame[0] == FRAME_CONTROL:
                        await socket.send_text(frame[1:].decode())
                    else:
                        await socket.send_bytes(frame)
                except RuntimeError:  # peer went away mid-send
                    continue

        return deliver

    def _update_deliverer(self, document_id: DocumentId):
        async def deliver(update: bytes) -> None:
            if not update:
                return
            frame = bytes([FRAME_UPDATE]) + update
            for socket in list(self._sockets.get(document_id, {})):
                try:
                    await socket.send_bytes(frame)
                except RuntimeError:  # peer went away mid-send
                    continue

        return deliver


async def _authenticate(socket: WebSocket) -> CallerContext:
    token = socket.query_params.get("token", "")
    if not token:
        raise NotAuthenticated("missing token")
    claims = await socket.app.state.container.token_port.verify(token)
    return CallerContext(
        user_id=UserId(claims.subject),
        tenant_id=TenantId(claims.tenant_id),
        email=claims.email,
        scopes=claims.scopes,
        is_service=claims.is_service,
    )


async def _handle_frame(
    socket: WebSocket,
    frame: bytes,
    *,
    caller: CallerContext,
    document_id: DocumentId,
    registry: DocumentPeers,
    socket_id: bytes,
) -> None:
    kind, payload = frame[0], frame[1:]
    if kind == FRAME_AWARENESS:
        await registry.publish(
            document_id, socket_id, bytes([FRAME_AWARENESS]) + payload
        )
        return
    if kind != FRAME_UPDATE:
        return  # unknown frame types are ignored (forward compatibility)
    use_cases = socket.app.state.container.use_cases
    try:
        # apply() publishes the raw update on the bus — the single live
        # fanout path shared with HTTP/MCP-originated edits. The sender
        # receives its own echo; Yjs re-application is a no-op.
        await use_cases.realtime.apply(caller, document_id, payload)
    except NotAuthorized:
        await socket.send_text(json.dumps({"type": "error", "error": "NotAuthorized"}))
        return


@router.websocket("/api/v1/documents/{document_id}/sync")
async def sync(socket: WebSocket, document_id: str) -> None:
    registry: DocumentPeers = socket.app.state.document_peers
    doc_id = DocumentId(document_id)
    try:
        caller = await _authenticate(socket)
        _, state = await socket.app.state.container.use_cases.realtime.join(
            caller, doc_id
        )
    except NotAuthenticated:
        await socket.close(code=4401)
        return
    except NotAuthorized:
        await socket.close(code=4403)
        return
    except NotFound:
        await socket.close(code=4404)
        return

    await socket.accept()
    socket_id = await registry.join(doc_id, socket)
    try:
        await socket.send_bytes(bytes([FRAME_UPDATE]) + state)
        while True:
            frame = await socket.receive_bytes()
            if frame:
                await _handle_frame(
                    socket,
                    frame,
                    caller=caller,
                    document_id=doc_id,
                    registry=registry,
                    socket_id=socket_id,
                )
    except WebSocketDisconnect:
        pass
    finally:
        await registry.leave(doc_id, socket)
        goodbye = json.dumps({"type": "presence_left", "user_id": caller.user_id})
        await registry.publish(
            doc_id, socket_id, bytes([FRAME_CONTROL]) + goodbye.encode()
        )
