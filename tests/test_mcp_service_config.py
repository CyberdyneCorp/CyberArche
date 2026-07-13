"""MCP deployable configuration (deployment regressions)."""

from __future__ import annotations

import pytest

import cyberarche.mcp_server.main as main
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


def test_wiring_maps_settings_to_the_composition_root():
    config = settings(
        backend="postgres",
        database_url="postgresql://db",
        auth_base_url="https://auth.test",
        auth_client_id="cid",
        auth_client_secret="sec",
        auth_audience="aud",
        rag_base_url="https://rag.test",
        rag_api_token="rag-token",
        dao_url="https://dao.test",
        llm_provider="anthropic",
        llm_model="claude-sonnet-5",
        llm_api_key="llm-key",
        llm_base_url="https://llm.test",
        connector_secret_key="k" * 32,
    ).wiring()

    assert config.backend == "postgres"
    assert config.database_url == "postgresql://db"
    assert config.auth_base_url == "https://auth.test"
    assert config.auth_client_id == "cid"
    assert config.auth_client_secret == "sec"
    assert config.auth_audience == "aud"
    assert config.auth_issuer == "cyberdyne-auth"
    assert config.rag_base_url == "https://rag.test"
    assert config.rag_api_token == "rag-token"
    assert config.dao_base_url == "https://dao.test"
    assert config.llm_api_key == "llm-key"
    assert config.llm_base_url == "https://llm.test"
    # F-001 regression: the MCP service must forward the secret key, or the
    # postgres composition root fails closed at startup.
    assert config.connector_secret_key == "k" * 32


def test_wiring_treats_unknown_backends_as_memory():
    assert settings(backend="sqlite").wiring().backend == "memory"


# ---- serve() ----------------------------------------------------------------


class FakeContainer:
    def __init__(self) -> None:
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


class FakeServer:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[dict] = []

    async def run_http_async(self, **kwargs) -> None:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error


def install_runtime(
    monkeypatch, server: FakeServer
) -> tuple[FakeContainer, dict]:
    container = FakeContainer()
    built: dict = {}

    async def fake_build_container(config):
        built["config"] = config
        return container

    monkeypatch.setattr(main, "build_container", fake_build_container)
    monkeypatch.setattr(main, "build_mcp_server", lambda c: server)
    return container, built


async def test_serve_without_allow_list_disables_host_protection(monkeypatch):
    server = FakeServer()
    container, built = install_runtime(monkeypatch, server)

    await main.serve(settings(backend="memory"))

    (call,) = server.calls
    assert call["host"] == "0.0.0.0"
    assert call["port"] == 8100
    assert call["host_origin_protection"] is False
    assert call["allowed_hosts"] is None
    assert call["uvicorn_config"] == {
        "proxy_headers": True,
        "forwarded_allow_ips": "*",
    }
    assert built["config"].backend == "memory"
    assert container.closed


async def test_serve_with_allow_list_enables_host_protection(monkeypatch):
    server = FakeServer()
    install_runtime(monkeypatch, server)

    await main.serve(settings(mcp_allowed_hosts="mcp.example"))

    (call,) = server.calls
    assert call["host_origin_protection"] is True
    assert "mcp.example" in call["allowed_hosts"]
    assert "127.0.0.1:8100" in call["allowed_hosts"]


async def test_serve_closes_the_container_when_the_server_crashes(monkeypatch):
    server = FakeServer(error=RuntimeError("boom"))
    container, _ = install_runtime(monkeypatch, server)

    with pytest.raises(RuntimeError, match="boom"):
        await main.serve(settings())

    assert container.closed


async def test_serve_builds_default_settings_when_none_given(monkeypatch):
    server = FakeServer()
    install_runtime(monkeypatch, server)
    monkeypatch.setattr(main, "McpSettings", lambda: settings(mcp_port=9999))

    await main.serve()

    assert server.calls[0]["port"] == 9999


def test_run_drives_serve_to_completion(monkeypatch):
    ran: list[bool] = []

    async def fake_serve() -> None:
        ran.append(True)

    monkeypatch.setattr(main, "serve", fake_serve)
    main.run()
    assert ran == [True]
