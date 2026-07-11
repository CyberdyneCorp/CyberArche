"""OpenAI image adapter: long timeout (gpt-image-1 is slow) + readable errors."""

from __future__ import annotations

import base64

import httpx
import pytest

from cyberarche.adapters.outbound.imagegen.openai_images import OpenAIImageGenerator


class _RecordingClient:
    """Minimal AsyncClient stand-in that captures the request kwargs."""

    def __init__(self, response: httpx.Response) -> None:
        self._response = response
        self.kwargs: dict | None = None

    async def post(self, url: str, **kwargs) -> httpx.Response:
        self.kwargs = kwargs
        return self._response


async def test_image_adapter_uses_a_long_timeout_and_returns_png():
    png = base64.b64encode(b"PNGDATA").decode()
    response = httpx.Response(
        200,
        json={"data": [{"b64_json": png}]},
        request=httpx.Request("POST", "https://api/images/generations"),
    )
    client = _RecordingClient(response)
    generator = OpenAIImageGenerator(client, api_key="k", model="gpt-image-1")  # type: ignore[arg-type]

    image = await generator.generate("a fox")

    assert image.content == b"PNGDATA"
    assert image.content_type == "image/png"
    # Regression: gpt-image-1 takes ~40s, so the shared client's 30s default cut
    # it off. The adapter must request its own longer budget.
    assert client.kwargs is not None and client.kwargs["timeout"] >= 60


async def test_image_adapter_surfaces_the_provider_error_message():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={"error": {"message": "Your prompt was rejected by the safety system."}},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    generator = OpenAIImageGenerator(client, api_key="k")

    with pytest.raises(RuntimeError, match="safety system"):
        await generator.generate("bad prompt")
    await client.aclose()
