"""architecture-quality 12.2: provider adapters selected purely by config."""

from __future__ import annotations

import pytest

from cyberarche.adapters.outbound.crypto import FernetSecretBox
from cyberarche.adapters.outbound.llm.anthropic import AnthropicLLM
from cyberarche.adapters.outbound.llm.openai_compatible import OpenAICompatibleLLM
from cyberarche.adapters.wiring import WiringConfig, build_container
from cyberarche.adapters.wiring import _build_secret_box
from cyberarche.application.testing.fakes import (
    InMemoryBlobStorage,
    InMemoryTaskQueue,
    InProcessPeerBus,
    NaiveSecretBox,
    StaticTokenPort,
)


async def build(**overrides):
    config = WiringConfig(backend="memory", **overrides)
    return await build_container(config, token_port=StaticTokenPort({}))


def test_secret_box_fails_closed_on_postgres_without_key():
    """F-001: the real backend must not silently fall back to non-encryption."""
    with pytest.raises(ValueError, match="connector_secret_key"):
        _build_secret_box(WiringConfig(backend="postgres", connector_secret_key=""))


def test_secret_box_allows_naive_only_on_memory_backend():
    box = _build_secret_box(WiringConfig(backend="memory", connector_secret_key=""))
    assert type(box).__name__ == "NaiveSecretBox"


def test_secret_box_uses_fernet_when_key_present():
    box = _build_secret_box(
        WiringConfig(backend="postgres", connector_secret_key="k" * 32)
    )
    assert isinstance(box, FernetSecretBox)


def test_fernet_rejects_weak_derivation_key():
    """F-016: a short passphrase (brute-forceable) is refused."""
    with pytest.raises(ValueError):
        FernetSecretBox("short")


def test_fernet_roundtrip_with_strong_key():
    box = FernetSecretBox("a-sufficiently-long-passphrase-of-32+chars")
    assert box.decrypt(box.encrypt("secret-value")) == "secret-value"


async def test_llm_provider_selected_by_config():
    anthropic = await build(llm_provider="anthropic", llm_api_key="k")
    local = await build(llm_provider="local", llm_base_url="http://ollama.local/v1")

    assert isinstance(anthropic.llm, AnthropicLLM)
    assert isinstance(local.llm, OpenAICompatibleLLM)
    await anthropic.aclose()
    await local.aclose()


async def test_secret_box_selected_by_config():
    fernet = await build(connector_secret_key="super-key-that-is-long-enough-32ch")
    naive = await build()

    assert isinstance(fernet.secret_box, FernetSecretBox)
    assert isinstance(naive.secret_box, NaiveSecretBox)
    # Round-trip through the real box.
    assert fernet.secret_box.decrypt(fernet.secret_box.encrypt("s")) == "s"
    await fernet.aclose()
    await naive.aclose()


async def test_shared_infra_defaults_to_single_process_implementations():
    container = await build()
    assert isinstance(container.blobs, InMemoryBlobStorage)
    assert isinstance(container.queue, InMemoryTaskQueue)
    assert isinstance(container.peer_bus, InProcessPeerBus)
    await container.aclose()


async def test_filesystem_blobs_selected_by_config(tmp_path):
    from cyberarche.adapters.outbound.objectstore.filesystem import (
        FilesystemBlobStorage,
    )

    container = await build(blob_dir=str(tmp_path / "blobs"))
    assert isinstance(container.blobs, FilesystemBlobStorage)
    await container.aclose()


# ---- auth stack, RAG, and optional tool adapters -----------------------------

import httpx

from cyberarche.adapters.outbound.auth.cyberdyne import (
    CyberdyneAuthGateway,
    IamAuthorization,
)
from cyberarche.adapters.outbound.rag.cyberdyne_rag import CyberdyneRagAdapter
from cyberarche.adapters.wiring import (
    SystemClock,
    UuidIds,
    _build_code_executor,
    _build_google_port,
    _build_image_generator,
    _build_meetings,
    _build_web_media,
)
from cyberarche.application.use_cases.api_keys import CompositeTokenVerifier
from cyberarche.application.testing.fakes import InMemoryRag, ScriptedLLM


def test_system_clock_and_uuid_ids():
    now = SystemClock().now()
    assert now.tzinfo is not None  # timezone-aware (UTC)
    ids = UuidIds()
    first, second = ids.new_id(), ids.new_id()
    assert first != second
    assert len(first) == 32  # uuid4().hex


async def test_missing_auth_config_without_injected_token_port_raises():
    with pytest.raises(ValueError):
        await build_container(WiringConfig(backend="memory"))


async def test_auth_stack_built_from_config():
    container = await build_container(
        WiringConfig(
            backend="memory",
            auth_base_url="https://auth.test",
            auth_client_id="cid",
            auth_client_secret="secret",
        )
    )
    # API keys wrap the JWKS verifier (design D-1).
    assert isinstance(container.token_port, CompositeTokenVerifier)
    assert container.service_tokens is not None
    assert isinstance(container.authorization, IamAuthorization)
    assert isinstance(container.auth_gateway, CyberdyneAuthGateway)
    await container.aclose()


async def test_injected_token_port_still_gets_api_key_seam():
    container = await build(auth_base_url="")
    assert isinstance(container.token_port, CompositeTokenVerifier)
    assert container.service_tokens is None
    assert container.authorization is None
    assert container.auth_gateway is None
    await container.aclose()


async def test_llm_defaults_to_scripted_fake_when_unconfigured():
    container = await build()
    assert isinstance(container.llm, ScriptedLLM)
    await container.aclose()


async def test_openai_provider_uses_openai_compatible_adapter():
    container = await build(llm_provider="openai", llm_api_key="k")
    assert isinstance(container.llm, OpenAICompatibleLLM)
    await container.aclose()


async def test_rag_defaults_to_in_memory_fake():
    container = await build()
    assert isinstance(container.rag, InMemoryRag)
    await container.aclose()


async def test_rag_adapter_selected_by_config_with_api_token():
    container = await build(rag_base_url="https://rag.test", rag_api_token="tok")
    assert isinstance(container.rag, CyberdyneRagAdapter)
    await container.aclose()


async def test_rag_adapter_falls_back_to_service_token():
    container = await build_container(
        WiringConfig(
            backend="memory",
            auth_base_url="https://auth.test",
            auth_client_id="cid",
            auth_client_secret="secret",
            rag_base_url="https://rag.test",
        )
    )
    assert isinstance(container.rag, CyberdyneRagAdapter)
    await container.aclose()


async def test_rag_without_token_or_credentials_raises():
    with pytest.raises(ValueError):
        await build(rag_base_url="https://rag.test")


async def test_optional_tool_adapters_disabled_by_default():
    http = httpx.AsyncClient()
    config = WiringConfig(backend="memory")
    assert _build_image_generator(config, http) is None
    assert _build_code_executor(config, None, lambda: http) is None
    assert _build_meetings(config, lambda: http) is None
    assert _build_web_media(config, lambda: http) is None
    assert _build_google_port(config, lambda: http) is None
    await http.aclose()


async def test_optional_tool_adapters_selected_by_config():
    from cyberarche.adapters.outbound.code_exec.cyberdyne_interpreter import (
        CyberdyneInterpreterAdapter,
    )
    from cyberarche.adapters.outbound.google.client import GoogleWorkspaceClient
    from cyberarche.adapters.outbound.imagegen.openai_images import OpenAIImageGenerator
    from cyberarche.adapters.outbound.meetings.cyberflies import (
        CyberfliesMeetingsAdapter,
    )
    from cyberarche.adapters.outbound.web_media.dao_backend import (
        DaoBackendWebMediaAdapter,
    )

    http = httpx.AsyncClient()

    class StubServiceTokens:
        async def service_token(self) -> str:
            return "svc-token"

    config = WiringConfig(
        backend="memory",
        image_api_key="ik",
        interpreter_base_url="https://interp.test",
        meetings_base_url="https://meet.test",
        dao_base_url="https://dao.test",
        google_client_id="gid",
        google_client_secret="gsecret",
        google_redirect_uri="https://app.test/callback",
    )
    assert isinstance(_build_image_generator(config, http), OpenAIImageGenerator)
    assert isinstance(
        _build_code_executor(config, StubServiceTokens(), lambda: http),
        CyberdyneInterpreterAdapter,
    )
    assert isinstance(_build_meetings(config, lambda: http), CyberfliesMeetingsAdapter)
    assert isinstance(_build_web_media(config, lambda: http), DaoBackendWebMediaAdapter)
    assert isinstance(_build_google_port(config, lambda: http), GoogleWorkspaceClient)
    await http.aclose()


async def test_web_media_wired_into_the_container():
    from cyberarche.adapters.outbound.web_media.dao_backend import (
        DaoBackendWebMediaAdapter,
    )

    container = await build(dao_base_url="https://dao.test")
    assert isinstance(container.web_media, DaoBackendWebMediaAdapter)
    await container.aclose()


async def test_injected_queue_and_peer_bus_win_over_built_ones():
    queue = InMemoryTaskQueue()
    bus = InProcessPeerBus()
    container = await build_container(
        WiringConfig(backend="memory"),
        token_port=StaticTokenPort({}),
        queue=queue,
        peer_bus=bus,
    )
    assert container.queue is queue
    assert container.peer_bus is bus
    await container.aclose()


async def test_redis_shared_infra_selected_by_config():
    from cyberarche.adapters.outbound.redis_infra.bus import RedisPeerBus
    from cyberarche.adapters.outbound.redis_infra.queue import RedisTaskQueue

    # from_url is lazy — nothing connects until the queue/bus are used.
    container = await build(redis_url="redis://localhost:6399/0")
    assert isinstance(container.queue, RedisTaskQueue)
    assert isinstance(container.peer_bus, RedisPeerBus)
    await container.aclose()


async def test_postgres_backend_selected_by_config(monkeypatch):
    import asyncpg

    from cyberarche.adapters.outbound.postgres.folders import PostgresFolderRepository
    from cyberarche.adapters.outbound.postgres.repositories import (
        PostgresDocumentRepository,
        PostgresWorkspaceRepository,
    )

    class FakePool:
        def __init__(self) -> None:
            self.closed = False

        async def close(self) -> None:
            self.closed = True

    pool = FakePool()
    seen: list[str] = []

    async def fake_create_pool(dsn: str) -> FakePool:
        seen.append(dsn)
        return pool

    monkeypatch.setattr(asyncpg, "create_pool", fake_create_pool)

    container = await build_container(
        WiringConfig(
            backend="postgres",
            database_url="postgresql://db/cyberarche",
            # Required now that the postgres backend fails closed without a key.
            connector_secret_key="k" * 32,
        ),
        token_port=StaticTokenPort({}),
    )
    assert seen == ["postgresql://db/cyberarche"]
    assert isinstance(container.workspaces, PostgresWorkspaceRepository)
    assert isinstance(container.documents, PostgresDocumentRepository)
    assert isinstance(container.folders, PostgresFolderRepository)

    # Shutdown closes the pool via the registered closer.
    await container.aclose()
    assert pool.closed
