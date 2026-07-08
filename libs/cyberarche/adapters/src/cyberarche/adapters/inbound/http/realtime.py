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

The relay holds no document state — peers per instance only; documents are
reconstructed from the persisted update log (stateless service rule).
"""

from __future__ import annotations

import json
from collections import defaultdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from cyberarche.application.kernel import CallerContext
from cyberarche.domain.errors import (
    NotAuthenticated,
    NotAuthorized,
    NotFound,
)
from cyberarche.domain.ids import DocumentId, TenantId, UserId

FRAME_UPDATE = 0x00
FRAME_AWARENESS = 0x01

router = APIRouter()


class DocumentPeers:
    """Per-instance registry of live connections per document."""

    def __init__(self) -> None:
        self._peers: dict[DocumentId, set[WebSocket]] = defaultdict(set)

    def join(self, document_id: DocumentId, socket: WebSocket) -> None:
        self._peers[document_id].add(socket)

    def leave(self, document_id: DocumentId, socket: WebSocket) -> None:
        self._peers[document_id].discard(socket)
        if not self._peers[document_id]:
            del self._peers[document_id]

    def others(self, document_id: DocumentId, socket: WebSocket) -> list[WebSocket]:
        return [peer for peer in self._peers.get(document_id, ()) if peer is not socket]


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


async def _broadcast(peers: list[WebSocket], frame: bytes) -> None:
    for peer in peers:
        try:
            await peer.send_bytes(frame)
        except RuntimeError:  # peer went away mid-send
            continue


async def _handle_frame(
    socket: WebSocket,
    frame: bytes,
    *,
    caller: CallerContext,
    document_id: DocumentId,
    registry: DocumentPeers,
) -> None:
    kind, payload = frame[0], frame[1:]
    if kind == FRAME_AWARENESS:
        await _broadcast(
            registry.others(document_id, socket), bytes([FRAME_AWARENESS]) + payload
        )
        return
    if kind != FRAME_UPDATE:
        return  # unknown frame types are ignored (forward compatibility)
    use_cases = socket.app.state.container.use_cases
    try:
        update = await use_cases.realtime.apply(caller, document_id, payload)
    except NotAuthorized:
        await socket.send_text(
            json.dumps({"type": "error", "error": "NotAuthorized"})
        )
        return
    await _broadcast(
        registry.others(document_id, socket), bytes([FRAME_UPDATE]) + update
    )


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
    registry.join(doc_id, socket)
    try:
        await socket.send_bytes(bytes([FRAME_UPDATE]) + state)
        while True:
            frame = await socket.receive_bytes()
            if frame:
                await _handle_frame(
                    socket, frame, caller=caller, document_id=doc_id, registry=registry
                )
    except WebSocketDisconnect:
        pass
    finally:
        registry.leave(doc_id, socket)
        for peer in registry.others(doc_id, socket):
            try:
                await peer.send_text(
                    json.dumps({"type": "presence_left", "user_id": caller.user_id})
                )
            except RuntimeError:
                continue
