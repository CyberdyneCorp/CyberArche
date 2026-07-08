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
    rag_base_url: str = "https://cyberrag.coolify.cyberdynecorp.ai"
    rag_api_token: str = ""
    rag_webhook_secret: str = ""
    llm_provider: str = "anthropic"
    llm_model: str = "claude-sonnet-5"
    llm_api_key: str = ""
    llm_base_url: str = ""
    connector_secret_key: str = ""
    redis_url: str = ""  # shared queue + realtime fanout for multi-replica
    blob_dir: str = ""  # filesystem blob storage; empty = in-memory
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
            rag_base_url=self.rag_base_url,
            rag_api_token=self.rag_api_token,
            rag_webhook_secret=self.rag_webhook_secret,
            llm_provider=self.llm_provider,
            llm_model=self.llm_model,
            llm_api_key=self.llm_api_key,
            llm_base_url=self.llm_base_url,
            connector_secret_key=self.connector_secret_key,
            redis_url=self.redis_url,
            blob_dir=self.blob_dir,
        )
