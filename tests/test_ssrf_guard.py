"""SSRF guard for external MCP connector endpoints (security audit F-002)."""

from __future__ import annotations

import pytest

from cyberarche.adapters.outbound.mcp_client.ssrf_guard import (
    EndpointNotAllowed,
    validate_endpoint,
)


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata
        "http://127.0.0.1:8100/",  # loopback
        "http://localhost/",  # loopback name
        "http://10.0.0.5/",  # private
        "http://192.168.1.1/",  # private
        "http://[::1]/",  # loopback v6
    ],
)
def test_internal_targets_are_rejected(endpoint):
    with pytest.raises(EndpointNotAllowed):
        validate_endpoint(endpoint, allow_private_networks=False)


@pytest.mark.parametrize("endpoint", ["file:///etc/passwd", "gopher://x/", "ftp://x/"])
def test_non_http_schemes_are_rejected(endpoint):
    with pytest.raises(EndpointNotAllowed):
        validate_endpoint(endpoint, allow_private_networks=False)


def test_public_https_endpoint_is_allowed():
    # example.com resolves to public addresses.
    validate_endpoint("https://example.com/mcp/", allow_private_networks=False)


def test_private_allowed_when_flag_set():
    # local/dev connectors legitimately point at loopback fixtures.
    validate_endpoint("http://127.0.0.1:8200/", allow_private_networks=True)


def test_missing_host_is_rejected():
    with pytest.raises(EndpointNotAllowed):
        validate_endpoint("https:///nohost", allow_private_networks=False)


async def test_adapter_guards_internal_endpoint_before_connecting():
    """The real adapter enforces the guard on every fetch, so a stored internal
    endpoint is blocked before any outbound connection (F-002)."""
    from cyberarche.adapters.outbound.mcp_client.fastmcp_client import (
        FastMcpClientAdapter,
    )

    adapter = FastMcpClientAdapter(allow_private_networks=False)
    with pytest.raises(EndpointNotAllowed):
        await adapter.list_tools("http://169.254.169.254/", "")
    with pytest.raises(EndpointNotAllowed):
        await adapter.call_tool("http://127.0.0.1:6379/", "", "t", {})


async def test_adapter_allows_private_when_permitted_flag_set(monkeypatch):
    """With the dev flag, the guard passes and the (unreachable) fixture host is
    reached — proving the guard, not connectivity, is what blocks."""
    from cyberarche.adapters.outbound.mcp_client import fastmcp_client

    adapter = fastmcp_client.FastMcpClientAdapter(allow_private_networks=True)
    # Guard passes; the connection itself will fail (nothing listening), which is
    # a different error class than EndpointNotAllowed.
    with pytest.raises(Exception) as excinfo:
        await adapter.list_tools("http://127.0.0.1:59999/", "")
    assert not isinstance(excinfo.value, EndpointNotAllowed)
