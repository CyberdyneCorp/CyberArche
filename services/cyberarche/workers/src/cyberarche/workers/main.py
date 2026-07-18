"""CyberArche workers deployable: queue consumer for ingestion and long
agent jobs. Same composition root as the API; scale horizontally by
running more replicas against the same Redis queue.
"""

from __future__ import annotations

import asyncio
import logging

from pydantic_settings import BaseSettings, SettingsConfigDict

from cyberarche.adapters.wiring import WiringConfig, build_container
from cyberarche.application.jobs import JobRunner, register_knowledge_jobs

logger = logging.getLogger("cyberarche.workers")


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CYBERARCHE_", env_file=".env", extra="ignore")

    backend: str = "memory"
    database_url: str = ""
    auth_base_url: str = "https://auth.backend.coolify.cyberdynecorp.ai"
    auth_client_id: str = ""
    auth_client_secret: str = ""
    auth_audience: str | None = None
    auth_issuer: str | None = None  # None => derive from auth_base_url
    auth_tenant_claim: str = "org_id"
    rag_base_url: str = "https://cyberrag.coolify.cyberdynecorp.ai"
    rag_api_token: str = ""
    llm_provider: str = "anthropic"
    llm_model: str = "claude-sonnet-5"
    llm_api_key: str = ""
    llm_base_url: str = ""
    connector_secret_key: str = ""
    redis_url: str = ""
    blob_dir: str = "./data/blobs"
    notification_webhook_url: str = ""

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
            llm_provider=self.llm_provider,
            llm_model=self.llm_model,
            llm_api_key=self.llm_api_key,
            llm_base_url=self.llm_base_url,
            connector_secret_key=self.connector_secret_key,
            redis_url=self.redis_url,
            blob_dir=self.blob_dir,
            notification_webhook_url=self.notification_webhook_url,
        )


async def serve(settings: WorkerSettings | None = None) -> None:
    settings = settings or WorkerSettings()
    container = await build_container(settings.wiring())
    runner = JobRunner(container.queue)
    register_knowledge_jobs(runner, container.use_cases.knowledge, container.blobs)
    logger.info("worker started (backend=%s)", settings.backend)
    try:
        await runner.run_forever()
    finally:
        await container.aclose()


def run() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(serve())


if __name__ == "__main__":
    run()
