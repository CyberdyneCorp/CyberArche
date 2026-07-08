"""MCP deployable configuration (deployment regressions)."""

from __future__ import annotations

from cyberarche.mcp_server.main import McpSettings


def settings(**overrides) -> McpSettings:
    base = {"mcp_allowed_hosts": "", "mcp_port": 8100, "auth_base_url": ""}
    return McpSettings(**{**base, **overrides})


def test_no_allow_list_disables_host_protection():
    """Proxy-only deployments (no FQDN configured) must not 421."""
    assert settings().allowed_hosts() is None


def test_allow_list_always_includes_loopback():
    """Regression: the container health check requests Host: 127.0.0.1:<port>.
    Allow-listing only the public FQDN made FastMCP answer 421, the container
    was marked unhealthy, and Traefik returned 502 on the public domain."""
    hosts = settings(mcp_allowed_hosts="cyberarche.mcp.coolify.cyberdynecorp.ai").allowed_hosts()

    assert hosts is not None
    assert "cyberarche.mcp.coolify.cyberdynecorp.ai" in hosts
    assert "127.0.0.1:8100" in hosts
    assert "127.0.0.1" in hosts


def test_multiple_public_hosts_are_supported():
    hosts = settings(mcp_allowed_hosts="a.example, b.example").allowed_hosts()

    assert hosts is not None
    assert hosts[:2] == ["a.example", "b.example"]
