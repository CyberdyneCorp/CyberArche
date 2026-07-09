"""file-uploads spec: image upload validation + membership-gated serve."""

from __future__ import annotations

PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def auth(token: str = "alice-token") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _workspace(api) -> dict:
    return api.post("/api/v1/workspaces", json={"name": "WS"}, headers=auth()).json()


def test_upload_and_serve_image(api):
    ws = _workspace(api)
    resp = api.post(
        f"/api/v1/workspaces/{ws['id']}/files",
        files={"file": ("a.png", PNG, "image/png")},
        headers=auth(),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["content_type"] == "image/png"
    assert body["url"] == f"/api/v1/workspaces/{ws['id']}/files/{body['id']}"

    served = api.get(body["url"], headers=auth())
    assert served.status_code == 200
    assert served.content == PNG
    assert served.headers["content-type"].startswith("image/png")


def test_reject_oversized_upload(api):
    ws = _workspace(api)
    big = PNG + b"\x00" * (10 * 1024 * 1024 + 1)
    resp = api.post(
        f"/api/v1/workspaces/{ws['id']}/files",
        files={"file": ("big.png", big, "image/png")},
        headers=auth(),
    )
    assert resp.status_code == 422


def test_reject_disguised_non_image(api):
    """A non-image whose declared content type claims PNG is rejected by the
    magic-byte check — otherwise a script payload could be served as an image."""
    ws = _workspace(api)
    fake = b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>"
    resp = api.post(
        f"/api/v1/workspaces/{ws['id']}/files",
        files={"file": ("x.png", fake, "image/png")},
        headers=auth(),
    )
    assert resp.status_code == 422


def test_non_member_cannot_serve_file(api):
    ws = _workspace(api)  # alice (acme) owns it
    body = api.post(
        f"/api/v1/workspaces/{ws['id']}/files",
        files={"file": ("a.png", PNG, "image/png")},
        headers=auth(),
    ).json()
    # mallory is a different tenant with no membership.
    denied = api.get(body["url"], headers=auth("mallory-token"))
    assert denied.status_code == 403
