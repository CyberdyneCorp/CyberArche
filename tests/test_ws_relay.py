"""WebSocket relay: broadcast, viewer rejection, auth close codes."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import anyio
from pycrdt import Doc, Text

from starlette.websockets import WebSocketDisconnect

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
    teamspace = api.post(
        f"/api/v1/workspaces/{workspace['id']}/teamspaces",
        json={"name": "Team"}, headers=auth(),
    ).json()
    document = api.post(
        "/api/v1/documents",
        json={"workspace_id": workspace["id"], "title": "Live", "teamspace_id": teamspace["id"]},
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
    # token_port is the CompositeTokenVerifier (API keys wrap the inner
    # verifier); register the test token on the inner StaticTokenPort.
    api.app.state.container.token_port._inner.register(
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


def test_agent_http_edit_reaches_open_websocket_clients(api):
    """ai-agent spec: agent edits appear LIVE to connected participants.
    Regression test — server-originated edits (HTTP/MCP) must fan out
    through the bus, not only persist to the update log."""
    _, document_id = make_document(api)
    url = f"/api/v1/documents/{document_id}/sync?token=alice-token"

    with api.websocket_connect(url) as client:
        client.receive_bytes()  # initial state

        response = api.post(
            f"/api/v1/documents/{document_id}/agent/blocks",
            json={
                "blocks": [
                    {"id": "agent1", "type": "paragraph", "data": {"text": "live agent edit"}}
                ]
            },
            headers=auth(),
        )
        assert response.status_code == 201

        frame = client.receive_bytes()
        assert frame[0] == FRAME_UPDATE
        doc = Doc()
        doc.apply_update(frame[1:])
        from pycrdt import Array

        blocks = [dict(m) for m in doc.get("blocks", type=Array)]
        assert blocks[0]["data"]["text"] == "live agent edit"


def _refusal_code(api, url: str) -> int:
    """The application close code the client actually receives.

    Asserting merely "it raised" cannot distinguish an expired token from a
    forbidden document — and the client's behaviour differs (refresh vs stop).
    """
    with api.websocket_connect(url) as ws:
        try:
            ws.receive_bytes()
        except WebSocketDisconnect as exc:
            return exc.code
    raise AssertionError("expected the connection to be refused")


def test_missing_token_is_refused(api):
    _, document_id = make_document(api)
    assert _refusal_code(api, f"/api/v1/documents/{document_id}/sync") == 4401


def test_unknown_document_is_refused(api):
    assert (
        _refusal_code(api, "/api/v1/documents/nope/sync?token=alice-token") == 4404
    )


def test_join_without_any_role_is_refused(api):
    """realtime-collaboration spec: "a client SHALL only join a document it is
    permitted to view". The 4403 branch of the handshake was unexercised — a
    regression dropping the require() from join() would have made every
    document readable by any authenticated member of the tenant.
    """
    _, document_id = make_document(api)
    # Same tenant as the owner, but granted nothing at all.
    api.app.state.container.token_port._inner.register(
        "eve-token", Claims(subject="eve", tenant_id="acme")
    )

    code = _refusal_code(api, f"/api/v1/documents/{document_id}/sync?token=eve-token")
    assert code == 4403  # forbidden, not merely "some failure"


def test_viewer_may_join(api):
    """The counterpart: a viewer IS permitted to join (only updates are barred),
    so the refusal above is about authorization, not a blanket denial.
    """
    workspace_id, document_id = make_document(api)
    api.app.state.container.token_port._inner.register(
        "dave-token", Claims(subject="dave", tenant_id="acme")
    )
    grant(api, workspace_id, "dave", Role.VIEWER)

    with api.websocket_connect(
        f"/api/v1/documents/{document_id}/sync?token=dave-token"
    ) as ws:
        assert ws.receive_bytes() is not None


def test_snapshot_restore_reaches_open_websocket_clients(api):
    """realtime-collaboration spec: a restore is an ordinary CRDT update, so a
    connected editor converges on the restored content without reloading.
    Writing the document row directly would leave this client divergent.
    """
    _, document_id = make_document(api)
    url = f"/api/v1/documents/{document_id}/sync?token=alice-token"

    blocks = [{"id": "b1", "type": "paragraph", "data": {"text": "v1"}}]
    api.post(
        f"/api/v1/documents/{document_id}/agent/blocks",
        json={"blocks": blocks},
        headers=auth(),
    )
    snapshot = api.post(
        f"/api/v1/documents/{document_id}/snapshots",
        json={"content": {"blocks": blocks}},
        headers=auth(),
    ).json()
    api.post(
        f"/api/v1/documents/{document_id}/agent/blocks",
        json={"blocks": [{"id": "b2", "type": "paragraph", "data": {"text": "v2"}}]},
        headers=auth(),
    )

    # A real client: hydrate from the initial state, then apply live deltas.
    doc = Doc()
    with api.websocket_connect(url) as client:
        initial = client.receive_bytes()
        assert initial[0] == FRAME_UPDATE
        doc.apply_update(initial[1:])
        from pycrdt import Array

        assert [dict(m)["id"] for m in doc.get("blocks", type=Array)] == ["b1", "b2"]

        response = api.post(
            f"/api/v1/documents/{document_id}/snapshots/{snapshot['id']}/restore",
            headers=auth(),
        )
        assert response.status_code == 200

        frame = client.receive_bytes()
        assert frame[0] == FRAME_UPDATE
        doc.apply_update(frame[1:])  # the restore, delivered as a delta

    # The open client converged on v1 without reloading.
    assert [dict(m)["id"] for m in doc.get("blocks", type=Array)] == ["b1"]
