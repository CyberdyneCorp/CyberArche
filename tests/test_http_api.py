"""HTTP surface: 401 seam, tenant non-spoofability, and the vertical flow."""

from __future__ import annotations

from pycrdt import Array, Doc


def auth(token: str = "alice-token") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _block_ids(api, document_id: str, headers: dict[str, str]) -> list[str]:
    """The document's live blocks. No HTTP endpoint reads them — the editor
    reads over the realtime socket, so a restore is only real if it shows up
    there."""
    url = f"/api/v1/documents/{document_id}/sync?token=alice-token"
    with api.websocket_connect(url) as client:
        frame = client.receive_bytes()  # FRAME_UPDATE + current state
    doc = Doc()
    doc.apply_update(frame[1:])
    return [dict(m).get("id") for m in doc.get("blocks", type=Array)]


def test_requests_without_token_get_401_before_any_use_case(api):
    assert api.get("/api/v1/workspaces").status_code == 401
    assert api.post("/api/v1/workspaces", json={"name": "X"}).status_code == 401


def test_invalid_token_gets_401(api):
    response = api.get("/api/v1/workspaces", headers=auth("forged-token"))
    assert response.status_code == 401


def test_tenant_comes_from_claims_not_body(api):
    """A tenant_id smuggled into the body is ignored (auth-integration spec)."""
    response = api.post(
        "/api/v1/workspaces",
        json={"name": "Spoofed", "tenant_id": "evil-corp"},
        headers=auth("alice-token"),
    )
    assert response.status_code == 201

    # Mallory (tenant globex) cannot see Alice's (tenant acme) workspace.
    mallory_view = api.get("/api/v1/workspaces", headers=auth("mallory-token"))
    assert mallory_view.json() == []


def test_vertical_flow_workspace_document_snapshot_trash_restore(api):
    headers = auth("alice-token")

    workspace = api.post(
        "/api/v1/workspaces", json={"name": "Eng"}, headers=headers
    ).json()

    parent = api.post(
        "/api/v1/documents",
        json={"workspace_id": workspace["id"], "title": "RFC-1"},
        headers=headers,
    ).json()
    child = api.post(
        "/api/v1/documents",
        json={"workspace_id": workspace["id"], "title": "Appendix", "parent_id": parent["id"]},
        headers=headers,
    ).json()

    children = api.get(
        "/api/v1/documents",
        params={"workspace_id": workspace["id"], "parent_id": parent["id"]},
        headers=headers,
    ).json()
    assert [c["id"] for c in children] == [child["id"]]

    # Snapshot the document, edit it, then restore over HTTP. Asserting only
    # `restored_from` (as this test once did) passes against a restore that
    # never touches the document — read the blocks back.
    v1_blocks = [{"id": "b1", "type": "paragraph", "data": {"text": "hello"}}]
    api.post(
        f"/api/v1/documents/{parent['id']}/agent/blocks",
        json={"blocks": v1_blocks},
        headers=headers,
    )
    snapshot = api.post(
        f"/api/v1/documents/{parent['id']}/snapshots",
        json={"content": {"blocks": v1_blocks}},
        headers=headers,
    ).json()

    api.post(
        f"/api/v1/documents/{parent['id']}/agent/blocks",
        json={"blocks": [{"id": "b2", "type": "paragraph", "data": {"text": "bye"}}]},
        headers=headers,
    )
    assert _block_ids(api, parent["id"], headers) == ["b1", "b2"]

    restored = api.post(
        f"/api/v1/documents/{parent['id']}/snapshots/{snapshot['id']}/restore",
        headers=headers,
    ).json()
    assert restored["restored_from"] == snapshot["id"]
    assert _block_ids(api, parent["id"], headers) == ["b1"]  # content really replaced

    assert api.delete(f"/api/v1/documents/{child['id']}", headers=headers).json()["trashed"]
    assert (
        api.post(f"/api/v1/documents/{child['id']}/restore", headers=headers)
        .json()["trashed"]
        is False
    )

    # Cross-tenant access is a 404, not a 403 (no resource existence leak).
    assert (
        api.get(f"/api/v1/documents/{parent['id']}", headers=auth("mallory-token")).status_code
        == 404
    )
