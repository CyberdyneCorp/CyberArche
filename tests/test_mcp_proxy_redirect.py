"""Regression: MCP behind a TLS-terminating proxy must not downgrade redirects.

FastMCP redirects `/mcp/` -> `/mcp` (307). Without uvicorn's proxy headers the
app believes the scheme is http, so the Location is `http://…`. MCP clients
(httpx) treat a scheme change as a new origin and STRIP the Authorization
header on the follow-up request — every tool call then fails with
"missing bearer token", even though /health looks fine.

The live check (TEST_MCP_URL) asserts the running server honours
X-Forwarded-Proto; the unit checks pin the settings that enable it.
"""

from __future__ import annotations

import os

import httpx
import pytest

from cyberarche.mcp_server.main import McpSettings


def settings(**overrides) -> McpSettings:
    return McpSettings(**{"auth_base_url": "", **overrides})


def test_proxy_headers_are_trusted_by_default():
    """The service is only reachable through the proxy, so its uvicorn must
    honour X-Forwarded-Proto (otherwise redirects downgrade to http)."""
    assert settings().mcp_forwarded_allow_ips == "*"


def test_allowed_hosts_include_loopback_for_health_checks():
    hosts = settings(mcp_allowed_hosts="mcp.example").allowed_hosts()
    assert hosts is not None
    assert "mcp.example" in hosts
    assert "127.0.0.1:8100" in hosts  # the container health check's Host


@pytest.mark.skipif(
    not os.environ.get("TEST_MCP_URL"),
    reason="TEST_MCP_URL (a running MCP server) not configured",
)
def test_live_redirect_preserves_the_forwarded_scheme():
    """POST /mcp/ redirects to /mcp; behind a proxy the Location must stay
    https, or clients silently drop their Authorization header."""
    base = os.environ["TEST_MCP_URL"].rstrip("/")
    response = httpx.post(
        f"{base}/mcp/",
        json={},
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "mcp.example",
        },
        follow_redirects=False,
        timeout=20.0,
    )

    if response.status_code in (307, 308):
        assert response.headers["location"].startswith("https://"), (
            "redirect downgraded to http -> MCP clients strip Authorization"
        )
