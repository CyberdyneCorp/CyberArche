"""API service settings (env-driven, CYBERARCHE_ prefix)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

from cyberarche.adapters.wiring import WiringConfig


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CYBERARCHE_", env_file=".env")

    backend: str = "memory"
    database_url: str = ""
    auth_base_url: str = "https://auth.backend.coolify.cyberdynecorp.ai"
    auth_client_id: str = ""
    auth_client_secret: str = ""
    auth_audience: str | None = None
    auth_tenant_claim: str = "org_id"
    cors_origins: list[str] = ["http://localhost:5173"]

    def wiring(self) -> WiringConfig:
        return WiringConfig(
            backend="postgres" if self.backend == "postgres" else "memory",
            database_url=self.database_url,
            auth_base_url=self.auth_base_url,
            auth_client_id=self.auth_client_id,
            auth_client_secret=self.auth_client_secret,
            auth_audience=self.auth_audience,
            auth_tenant_claim=self.auth_tenant_claim,
        )
