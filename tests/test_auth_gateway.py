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
