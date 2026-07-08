"""CyberArche MCP server deployable (FastMCP over HTTP).

Same composition root as the API service; stateless, horizontally scalable.
"""

from __future__ import annotations

import asyncio

from pydantic_settings import BaseSettings, SettingsConfigDict

from cyberarche.adapters.inbound.mcp.server import build_mcp_server
from cyberarche.adapters.wiring import WiringConfig, build_container


class McpSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CYBERARCHE_", env_file=".env", extra="ignore")

    backend: str = "memory"
    database_url: str = ""
    auth_base_url: str = "https://auth.backend.coolify.cyberdynecorp.ai"
    auth_client_id: str = ""
    auth_client_secret: str = ""
    auth_audience: str | None = None
    auth_tenant_claim: str = "org_id"
    rag_base_url: str = "https://cyberrag.coolify.cyberdynecorp.ai"
    rag_api_token: str = ""
    llm_provider: str = "anthropic"
    llm_model: str = "claude-sonnet-5"
    llm_api_key: str = ""
    llm_base_url: str = ""
    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8100
    # Behind a reverse proxy (Traefik/Coolify) the Host header is the public
    # FQDN. FastMCP's DNS-rebinding protection rejects unknown hosts with 421,
    # so the deployment must allow-list its domain (comma-separated).
    mcp_allowed_hosts: str = ""

    def wiring(self) -> WiringConfig:
        return WiringConfig(
            backend="postgres" if self.backend == "postgres" else "memory",
            database_url=self.database_url,
            auth_base_url=self.auth_base_url,
            auth_client_id=self.auth_client_id,
            auth_client_secret=self.auth_client_secret,
            auth_audience=self.auth_audience,
            auth_tenant_claim=self.auth_tenant_claim,
            rag_base_url=self.rag_base_url,
            rag_api_token=self.rag_api_token,
            llm_provider=self.llm_provider,
            llm_model=self.llm_model,
            llm_api_key=self.llm_api_key,
            llm_base_url=self.llm_base_url,
        )

    def allowed_hosts(self) -> list[str] | None:
        """Configured public FQDNs plus loopback.

        The container's own health check requests Host: 127.0.0.1:<port>;
        omitting it makes FastMCP answer 421, the container is marked
        unhealthy, and Traefik skips it -> 502 on the public domain.
        """
        hosts = [h.strip() for h in self.mcp_allowed_hosts.split(",") if h.strip()]
        if not hosts:
            return None
        loopback = [
            "127.0.0.1",
            "localhost",
            f"127.0.0.1:{self.mcp_port}",
            f"localhost:{self.mcp_port}",
        ]
        return hosts + [h for h in loopback if h not in hosts]


async def serve(settings: McpSettings | None = None) -> None:
    settings = settings or McpSettings()
    container = await build_container(settings.wiring())
    try:
        server = build_mcp_server(container)
        hosts = settings.allowed_hosts()
        await server.run_http_async(
            host=settings.mcp_host,
            port=settings.mcp_port,
            # No allow-list configured -> disable host protection (the service
            # is only reachable through the proxy in that deployment).
            host_origin_protection=hosts is not None,
            allowed_hosts=hosts,
        )
    finally:
        await container.aclose()


def run() -> None:
    asyncio.run(serve())


if __name__ == "__main__":
    run()
