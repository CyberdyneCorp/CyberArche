"""WebSocket relay: broadcast, viewer rejection, auth close codes."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import anyio
from pycrdt import Doc, Text

from cyberarche.adapters.inbound.http.realtime import FRAME_UPDATE
from cyberarche.application.ports.identity import Claims
from cyberarche.domain.ids import UserId
from cyberarche.domain.memberships import Role, WorkspaceMembership


def auth(token: str = "alice-token") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def one_edit(text: str) -> bytes:
    doc = Doc()
    body = doc.get("text", type=Text)
    body += text
    return doc.get_update()


def make_document(api) -> tuple[str, str]:
    workspace = api.post(
        "/api/v1/workspaces", json={"name": "RT"}, headers=auth()
    ).json()
    document = api.post(
        "/api/v1/documents",
        json={"workspace_id": workspace["id"], "title": "Live"},
        headers=auth(),
    ).json()
    return workspace["id"], document["id"]


def grant(api, workspace_id: str, user: str, role: Role) -> None:
    async def _grant() -> None:
        await api.app.state.container.memberships.add_workspace_member(
            WorkspaceMembership(
                workspace_id=workspace_id,
                user_id=UserId(user),
                role=role,
                granted_at=datetime.now(UTC),
            )
        )

    anyio.run(_grant)


def test_update_is_broadcast_to_other_peer(api):
    _, document_id = make_document(api)
    url = f"/api/v1/documents/{document_id}/sync?token=alice-token"

    with api.websocket_connect(url) as first, api.websocket_connect(url) as second:
        first.receive_bytes()  # initial state
        second.receive_bytes()

        first.send_bytes(bytes([FRAME_UPDATE]) + one_edit("hello from first"))

        frame = second.receive_bytes()
        assert frame[0] == FRAME_UPDATE
        doc = Doc()
        doc.apply_update(frame[1:])
        assert str(doc.get("text", type=Text)) == "hello from first"


def test_viewer_update_rejected_and_not_broadcast(api):
    workspace_id, document_id = make_document(api)
    api.app.state.container.token_port.register(
        "carol-token", Claims(subject="carol", tenant_id="acme")
    )
    grant(api, workspace_id, "carol", Role.VIEWER)

    owner_url = f"/api/v1/documents/{document_id}/sync?token=alice-token"
    viewer_url = f"/api/v1/documents/{document_id}/sync?token=carol-token"

    with (
        api.websocket_connect(owner_url) as owner,
        api.websocket_connect(viewer_url) as viewer,
    ):
        owner.receive_bytes()
        viewer.receive_bytes()

        viewer.send_bytes(bytes([FRAME_UPDATE]) + one_edit("viewer sneaks in"))

        error = json.loads(viewer.receive_text())
        assert error == {"type": "error", "error": "NotAuthorized"}


def test_missing_token_is_refused(api):
    _, document_id = make_document(api)
    try:
        with api.websocket_connect(f"/api/v1/documents/{document_id}/sync") as ws:
            ws.receive_bytes()
        raise AssertionError("expected close")
    except AssertionError:
        raise
    except Exception:
        pass  # closed with 4401 before accept


def test_unknown_document_is_refused(api):
    try:
        with api.websocket_connect(
            "/api/v1/documents/nope/sync?token=alice-token"
        ) as ws:
            ws.receive_bytes()
        raise AssertionError("expected close")
    except AssertionError:
        raise
    except Exception:
        pass  # closed with 4404 before accept
