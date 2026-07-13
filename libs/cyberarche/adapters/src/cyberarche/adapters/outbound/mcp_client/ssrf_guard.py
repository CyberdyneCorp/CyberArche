"""SSRF guard for external MCP connector endpoints.

A connector endpoint is an arbitrary user-supplied URL that the server fetches
(on registration and on every later agent run). Without validation this is a
server-side request forgery surface: an authenticated caller could point it at
cloud metadata (169.254.169.254), loopback, or internal service names and use
the handshake outcome as a blind internal port scanner (security audit F-002).

This module rejects non-http(s) schemes and hosts that resolve to loopback,
private, link-local, or otherwise non-public addresses. Private networks are
allowed only when explicitly permitted (local/dev, where connectors legitimately
point at 127.0.0.1 test fixtures).
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


class EndpointNotAllowed(ValueError):
    """The connector endpoint is not a permitted target."""


def _resolved_addresses(host: str) -> list[ipaddress._BaseAddress]:
    # getaddrinfo covers A/AAAA and literal IPs; every result must be public.
    infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    return [ipaddress.ip_address(info[4][0]) for info in infos]


def _is_public(address: ipaddress._BaseAddress) -> bool:
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def validate_endpoint(endpoint: str, *, allow_private_networks: bool = False) -> None:
    """Raise EndpointNotAllowed unless `endpoint` is a safe outbound target.

    Resolves the host and rejects it if any resolved address is non-public, so a
    DNS name pointing at an internal address is caught too. Re-run at fetch time
    (not only at registration) to stay safe against DNS rebinding.
    """
    parsed = urlparse(endpoint)
    if parsed.scheme not in ("http", "https"):
        raise EndpointNotAllowed(
            f"endpoint scheme {parsed.scheme!r} is not allowed (use https)"
        )
    host = parsed.hostname
    if not host:
        raise EndpointNotAllowed("endpoint has no host")
    if allow_private_networks:
        return
    try:
        addresses = _resolved_addresses(host)
    except socket.gaierror as error:
        raise EndpointNotAllowed(f"endpoint host {host!r} did not resolve") from error
    if not addresses or any(not _is_public(addr) for addr in addresses):
        raise EndpointNotAllowed(
            f"endpoint host {host!r} resolves to a non-public address"
        )
