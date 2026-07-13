"""API service settings (env-driven, CYBERARCHE_ prefix)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

from cyberarche.adapters.wiring import WiringConfig


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CYBERARCHE_", env_file=".env", extra="ignore")

    backend: str = "memory"
    database_url: str = ""
    auth_base_url: str = "https://auth.backend.coolify.cyberdynecorp.ai"
    auth_client_id: str = ""
    auth_client_secret: str = ""
    auth_audience: str | None = None
    auth_issuer: str | None = "cyberdyne-auth"
    auth_tenant_claim: str = "org_id"
    rag_base_url: str = "https://cyberrag.coolify.cyberdynecorp.ai"
    rag_api_token: str = ""
    rag_webhook_secret: str = ""
    llm_provider: str = "anthropic"
    llm_model: str = "claude-sonnet-5"
    llm_api_key: str = ""
    llm_base_url: str = ""
    image_api_key: str = ""  # enables the agent's generate_image tool
    image_model: str = "gpt-image-1"
    image_base_url: str = ""
    # Cyberdyne Python Interpreter (agent run_python tool); needs CyberdyneAuth
    # service-token credentials to authenticate. Empty disables the tool.
    interpreter_url: str = "https://interpreter.backend.coolify.cyberdynecorp.ai"
    # Cyberflies meeting transcripts (agent meeting tools). Called with the
    # caller's own access token; empty disables the tools.
    meetings_url: str = "https://cyberflies.backend.coolify.cyberdynecorp.ai"
    # DAO backend for agent web search + YouTube tools. Called with the caller's
    # own forwarded access token; empty disables the tools.
    dao_url: str = "https://dao.backend.coolify.cyberdynecorp.ai"
    # Google Workspace connector OAuth (Gmail/Calendar/Docs). Empty = disabled.
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = ""
    connector_secret_key: str = ""
    redis_url: str = ""  # shared queue + realtime fanout for multi-replica
    blob_dir: str = ""  # filesystem blob storage; empty = in-memory
    cors_origins: list[str] = ["http://localhost:5173"]
    # Autonomous agents: the in-process scheduler that runs due tasks (postgres
    # deployments only). Disable to run the API without background execution.
    enable_scheduler: bool = True
    scheduler_interval_seconds: int = 60

    def wiring(self) -> WiringConfig:
        return WiringConfig(
            backend="postgres" if self.backend == "postgres" else "memory",
            database_url=self.database_url,
            auth_base_url=self.auth_base_url,
            auth_client_id=self.auth_client_id,
            auth_client_secret=self.auth_client_secret,
            auth_audience=self.auth_audience,
            auth_issuer=self.auth_issuer,
            auth_tenant_claim=self.auth_tenant_claim,
            rag_base_url=self.rag_base_url,
            rag_api_token=self.rag_api_token,
            rag_webhook_secret=self.rag_webhook_secret,
            llm_provider=self.llm_provider,
            llm_model=self.llm_model,
            llm_api_key=self.llm_api_key,
            llm_base_url=self.llm_base_url,
            image_api_key=self.image_api_key,
            image_model=self.image_model,
            image_base_url=self.image_base_url,
            interpreter_base_url=self.interpreter_url,
            meetings_base_url=self.meetings_url,
            dao_base_url=self.dao_url,
            google_client_id=self.google_client_id,
            google_client_secret=self.google_client_secret,
            google_redirect_uri=self.google_redirect_uri,
            connector_secret_key=self.connector_secret_key,
            redis_url=self.redis_url,
            blob_dir=self.blob_dir,
        )
