"""Health router: the liveness endpoint sits before the auth seam."""

from __future__ import annotations


def test_health_returns_ok(api):
    response = api.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_requires_no_token(api):
    # Load balancers probe unauthenticated: even a forged token must not 401.
    response = api.get(
        "/api/v1/health", headers={"Authorization": "Bearer forged-token"}
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
