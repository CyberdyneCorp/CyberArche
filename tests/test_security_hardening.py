"""HTTP hardening: security headers, CORS guard, auth rate limit
(security audit F-005, F-006, INFO-1)."""

from __future__ import annotations

import pytest

from cyberarche.api.bootstrap import create_app
from cyberarche.api.config import Settings

from tests.conftest import TOKENS
from cyberarche.application.testing.fakes import StaticTokenPort


def test_security_headers_present(api):
    response = api.get("/api/v1/health")
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert "Strict-Transport-Security" in response.headers


def test_credentialed_wildcard_cors_is_refused_at_startup():
    with pytest.raises(ValueError, match="CORS"):
        create_app(
            Settings(backend="memory", auth_base_url="", cors_origins=["*"]),
            token_port=StaticTokenPort(dict(TOKENS)),
        )


def test_auth_endpoint_is_rate_limited(api):
    # The credential proxy is throttled; the 11th attempt in the window is 429.
    seen_429 = False
    for _ in range(15):
        response = api.post(
            "/api/v1/auth/session", json={"email": "u@t.io", "password": "pw"}
        )
        if response.status_code == 429:
            seen_429 = True
            assert response.headers.get("Retry-After")
            break
    assert seen_429


def test_non_auth_endpoints_are_not_rate_limited(api):
    # Health is not in the limited prefix — many calls stay 200.
    for _ in range(30):
        assert api.get("/api/v1/health").status_code == 200


def test_refresh_endpoint_is_not_rate_limited(api):
    """Regression (prod incident 2026-07-17): the SPA calls /session/refresh on
    every load and after any 401, so it must NOT be throttled — only login is.
    Throttling refresh 429'd normal use and locked users out."""
    codes = set()
    for _ in range(20):
        codes.add(api.post("/api/v1/auth/session/refresh").status_code)
    assert 429 not in codes  # never rate-limited (401 without a cookie is fine)


def test_rate_limit_is_keyed_per_client_ip(api):
    """Regression: the limiter must key on the real client IP (X-Forwarded-For),
    not the shared proxy IP — otherwise one client's attempts 429 everyone."""
    # Client A burns its budget.
    a = {"X-Forwarded-For": "203.0.113.1"}
    for _ in range(15):
        api.post("/api/v1/auth/session", json={"email": "a@t.io", "password": "x"}, headers=a)
    assert (
        api.post(
            "/api/v1/auth/session", json={"email": "a@t.io", "password": "x"}, headers=a
        ).status_code
        == 429
    )
    # Client B (different forwarded IP) is unaffected.
    b = {"X-Forwarded-For": "203.0.113.2"}
    assert (
        api.post(
            "/api/v1/auth/session", json={"email": "b@t.io", "password": "x"}, headers=b
        ).status_code
        != 429
    )


def test_rate_limited_429_still_carries_cors_headers(api):
    """Regression (prod incident 2026-07-17): the rate limiter must sit INSIDE
    CORS, so a short-circuited 429 still gets Access-Control-Allow-Origin —
    otherwise the browser reports a CORS failure and the SPA can't read the 429
    to back off."""
    origin = "http://localhost:5173"  # the api fixture's allowed origin
    last = None
    for _ in range(15):
        last = api.post(
            "/api/v1/auth/session",
            json={"email": "u@t.io", "password": "pw"},
            headers={"Origin": origin},
        )
        if last.status_code == 429:
            break
    assert last is not None and last.status_code == 429
    assert last.headers.get("access-control-allow-origin") == origin
