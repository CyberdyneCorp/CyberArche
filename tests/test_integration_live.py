"""Live integration pass: real Postgres + real CyberdyneAuth.

Skipped unless the environment provides:
  TEST_DATABASE_URL       postgres://... (dedicated test database)
  CYBERARCHE_IT_AUTH_URL  CyberdyneAuth base URL
  CYBERARCHE_IT_EMAIL     test-user email
  CYBERARCHE_IT_PASSWORD  test-user password  (env only — never committed)

Verifies what the unit suite cannot: our JWKS verification against the
real signing keys, and the full HTTP vertical over real Postgres with a
real bearer token.
"""

from __future__ import annotations

import os
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from cyberarche.api.bootstrap import create_app
from cyberarche.api.config import Settings

REQUIRED = (
    "TEST_DATABASE_URL",
    "CYBERARCHE_IT_AUTH_URL",
    "CYBERARCHE_IT_EMAIL",
    "CYBERARCHE_IT_PASSWORD",
)

pytestmark = pytest.mark.skipif(
    any(not os.environ.get(name) for name in REQUIRED),
    reason="live integration env (TEST_DATABASE_URL, CYBERARCHE_IT_*) not configured",
)


@pytest.fixture(scope="module")
def live_token() -> str:
    response = httpx.post(
        f"{os.environ['CYBERARCHE_IT_AUTH_URL'].rstrip('/')}/api/v1/auth/login",
        json={
            "email": os.environ["CYBERARCHE_IT_EMAIL"],
            "password": os.environ["CYBERARCHE_IT_PASSWORD"],
        },
        timeout=15.0,
    )
    response.raise_for_status()
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def live_api() -> TestClient:
    settings = Settings(
        backend="postgres",
        database_url=os.environ["TEST_DATABASE_URL"],
        auth_base_url=os.environ["CYBERARCHE_IT_AUTH_URL"],
        rag_base_url="",  # RAG stays faked in this pass
    )
    with TestClient(create_app(settings)) as client:
        yield client


async def test_live_jwt_verifies_against_real_jwks(live_token):
    from cyberarche.adapters.outbound.auth.cyberdyne import (
        CyberdyneAuthConfig,
        JwksTokenVerifier,
    )

    config = CyberdyneAuthConfig(base_url=os.environ["CYBERARCHE_IT_AUTH_URL"])
    async with httpx.AsyncClient(timeout=15.0) as http:
        verifier = JwksTokenVerifier(config, http)
        claims = await verifier.verify(live_token)

    assert claims.subject  # real user id
    assert claims.tenant_id == claims.subject  # no org claim -> personal tenant


async def test_live_tampered_token_is_rejected(live_token):
    from cyberarche.adapters.outbound.auth.cyberdyne import (
        CyberdyneAuthConfig,
        JwksTokenVerifier,
    )
    from cyberarche.domain.errors import NotAuthenticated

    config = CyberdyneAuthConfig(base_url=os.environ["CYBERARCHE_IT_AUTH_URL"])
    header, payload, signature = live_token.split(".")
    forged = f"{header}.{payload}.{signature[:-4]}AAAA"
    async with httpx.AsyncClient(timeout=15.0) as http:
        with pytest.raises(NotAuthenticated):
            await JwksTokenVerifier(config, http).verify(forged)


def test_live_vertical_flow_on_postgres_with_real_auth(live_api, live_token):
    headers = {"Authorization": f"Bearer {live_token}"}
    marker = uuid.uuid4().hex[:8]

    # 401 seam with garbage token, real verifier.
    assert live_api.get("/api/v1/workspaces", headers={"Authorization": "Bearer x.y.z"}).status_code == 401

    workspace = live_api.post(
        "/api/v1/workspaces", json={"name": f"IT {marker}"}, headers=headers
    )
    assert workspace.status_code == 201, workspace.text
    workspace = workspace.json()

    document = live_api.post(
        "/api/v1/documents",
        json={"workspace_id": workspace["id"], "title": f"Doc {marker}"},
        headers=headers,
    ).json()
    child = live_api.post(
        "/api/v1/documents",
        json={
            "workspace_id": workspace["id"],
            "title": "Child",
            "parent_id": document["id"],
        },
        headers=headers,
    ).json()

    children = live_api.get(
        "/api/v1/documents",
        params={"workspace_id": workspace["id"], "parent_id": document["id"]},
        headers=headers,
    ).json()
    assert [c["id"] for c in children] == [child["id"]]

    snapshot = live_api.post(
        f"/api/v1/documents/{document['id']}/snapshots",
        json={"content": {"blocks": [{"type": "paragraph", "text": marker}]}},
        headers=headers,
    ).json()
    restored = live_api.post(
        f"/api/v1/documents/{document['id']}/snapshots/{snapshot['id']}/restore",
        headers=headers,
    ).json()
    assert restored["restored_from"] == snapshot["id"]

    assert live_api.delete(
        f"/api/v1/documents/{child['id']}", headers=headers
    ).json()["trashed"]
    assert (
        live_api.post(f"/api/v1/documents/{child['id']}/restore", headers=headers)
        .json()["trashed"]
        is False
    )


def test_live_realtime_sync_over_postgres(live_api, live_token):
    from pycrdt import Doc, Text

    headers = {"Authorization": f"Bearer {live_token}"}
    workspace = live_api.post(
        "/api/v1/workspaces", json={"name": f"RT {uuid.uuid4().hex[:8]}"}, headers=headers
    ).json()
    document = live_api.post(
        "/api/v1/documents",
        json={"workspace_id": workspace["id"], "title": "Live"},
        headers=headers,
    ).json()

    url = f"/api/v1/documents/{document['id']}/sync?token={live_token}"
    with live_api.websocket_connect(url) as first, live_api.websocket_connect(
        url
    ) as second:
        first.receive_bytes()
        second.receive_bytes()

        doc = Doc()
        text = doc.get("text", type=Text)
        text += "postgres-backed live edit"
        first.send_bytes(bytes([0]) + doc.get_update())

        frame = second.receive_bytes()
        received = Doc()
        received.apply_update(frame[1:])
        assert str(received.get("text", type=Text)) == "postgres-backed live edit"
