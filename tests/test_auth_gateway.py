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


def test_session_login_over_http_returns_bearer_pair(api):
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
    assert response.json() == {
        "access_token": "a-token",
        "refresh_token": "r-token",
        "token_type": "bearer",
    }


def test_session_refresh_over_http_rotates_tokens(api):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/auth/refresh"
        return httpx.Response(200, json={"access_token": "a2", "refresh_token": "r2"})

    api.app.state.container.auth_gateway = gateway_with(handler)
    response = api.post(
        "/api/v1/auth/session/refresh", json={"refresh_token": "r-token"}
    )
    assert response.status_code == 200
    assert response.json() == {
        "access_token": "a2",
        "refresh_token": "r2",
        "token_type": "bearer",
    }


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
