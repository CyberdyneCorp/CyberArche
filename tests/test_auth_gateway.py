"""SPA session gateway: login/refresh proxied to CyberdyneAuth."""

from __future__ import annotations

import httpx
import pytest

from cyberarche.adapters.outbound.auth.cyberdyne import (
    CyberdyneAuthConfig,
    CyberdyneAuthGateway,
)
from cyberarche.domain.errors import NotAuthenticated

CONFIG = CyberdyneAuthConfig(base_url="https://auth.test")


def gateway_with(handler) -> CyberdyneAuthGateway:
    return CyberdyneAuthGateway(
        CONFIG, httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )


async def test_password_login_returns_token_pair():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/auth/login"
        return httpx.Response(
            200, json={"access_token": "a-token", "refresh_token": "r-token"}
        )

    pair = await gateway_with(handler).password_login(email="u@t.io", password="pw")
    assert (pair.access_token, pair.refresh_token) == ("a-token", "r-token")


async def test_bad_credentials_rejected():
    handler = lambda request: httpx.Response(401, json={"detail": "nope"})  # noqa: E731
    with pytest.raises(NotAuthenticated):
        await gateway_with(handler).password_login(email="u@t.io", password="bad")


async def test_refresh_rotates_tokens():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/auth/refresh"
        return httpx.Response(
            200, json={"access_token": "a2", "refresh_token": "r2"}
        )

    pair = await gateway_with(handler).refresh(refresh_token="r-token")
    assert (pair.access_token, pair.refresh_token) == ("a2", "r2")


def test_session_endpoint_unconfigured_returns_404(api):
    """Memory/test deployments without an auth service expose no login."""
    response = api.post(
        "/api/v1/auth/session", json={"email": "u@t.io", "password": "pw"}
    )
    assert response.status_code == 404


def test_refresh_endpoint_unconfigured_returns_404(api):
    response = api.post(
        "/api/v1/auth/session/refresh", json={"refresh_token": "r-token"}
    )
    assert response.status_code == 404


def test_session_login_returns_access_only_and_sets_refresh_cookie(api):
    """F-004: login returns only the access token in the body; the refresh token
    is set as an HttpOnly cookie, never exposed to JS."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/auth/login"
        return httpx.Response(
            200, json={"access_token": "a-token", "refresh_token": "r-token"}
        )

    api.app.state.container.auth_gateway = gateway_with(handler)
    response = api.post(
        "/api/v1/auth/session", json={"email": "u@t.io", "password": "pw"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body == {"access_token": "a-token", "token_type": "bearer"}
    assert "refresh_token" not in body  # never in the JS-visible body
    cookie = response.headers.get("set-cookie", "")
    assert "cyberarche_refresh=r-token" in cookie
    assert "httponly" in cookie.lower()
    assert "samesite=strict" in cookie.lower()
    assert "path=/api/v1/auth/session" in cookie.lower()


def test_session_refresh_reads_cookie_and_rotates_it(api):
    """F-004: refresh uses the HttpOnly cookie (not a request body) and rotates
    the cookie; the body carries only the new access token."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/auth/refresh"
        # The gateway is called with the token taken from the cookie.
        return httpx.Response(200, json={"access_token": "a2", "refresh_token": "r2"})

    api.app.state.container.auth_gateway = gateway_with(handler)
    response = api.post(
        "/api/v1/auth/session/refresh", cookies={"cyberarche_refresh": "r-token"}
    )
    assert response.status_code == 200
    assert response.json() == {"access_token": "a2", "token_type": "bearer"}
    assert "cyberarche_refresh=r2" in response.headers.get("set-cookie", "")


def test_session_refresh_without_cookie_is_401(api):
    api.app.state.container.auth_gateway = gateway_with(
        lambda request: httpx.Response(200, json={"access_token": "x", "refresh_token": "y"})
    )
    response = api.post("/api/v1/auth/session/refresh")
    assert response.status_code == 401


def test_session_logout_clears_the_refresh_cookie(api):
    response = api.post(
        "/api/v1/auth/session/logout", cookies={"cyberarche_refresh": "r-token"}
    )
    assert response.status_code == 204
    cookie = response.headers.get("set-cookie", "")
    # Cleared: max-age 0 / expired.
    assert "cyberarche_refresh=" in cookie
    assert 'max-age=0' in cookie.lower() or 'expires=' in cookie.lower()


def test_session_bad_credentials_over_http_is_401(api):
    handler = lambda request: httpx.Response(401, json={"detail": "nope"})  # noqa: E731
    api.app.state.container.auth_gateway = gateway_with(handler)
    response = api.post(
        "/api/v1/auth/session", json={"email": "u@t.io", "password": "bad"}
    )
    assert response.status_code == 401
    assert response.json()["error"] == "NotAuthenticated"


def test_session_rejects_malformed_email(api):
    """Validation fails before the gateway is ever consulted."""
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"access_token": "a", "refresh_token": "r"})

    api.app.state.container.auth_gateway = gateway_with(handler)
    response = api.post(
        "/api/v1/auth/session", json={"email": "not-an-email", "password": "pw"}
    )
    assert response.status_code == 422
    assert calls == []
