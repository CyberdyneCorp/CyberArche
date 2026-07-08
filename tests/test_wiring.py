"""architecture-quality 12.2: provider adapters selected purely by config."""

from __future__ import annotations

from cyberarche.adapters.outbound.crypto import FernetSecretBox
from cyberarche.adapters.outbound.llm.anthropic import AnthropicLLM
from cyberarche.adapters.outbound.llm.openai_compatible import OpenAICompatibleLLM
from cyberarche.adapters.wiring import WiringConfig, build_container
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


async def test_llm_provider_selected_by_config():
    anthropic = await build(llm_provider="anthropic", llm_api_key="k")
    local = await build(llm_provider="local", llm_base_url="http://ollama.local/v1")

    assert isinstance(anthropic.llm, AnthropicLLM)
    assert isinstance(local.llm, OpenAICompatibleLLM)
    await anthropic.aclose()
    await local.aclose()


async def test_secret_box_selected_by_config():
    fernet = await build(connector_secret_key="super-key")
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
