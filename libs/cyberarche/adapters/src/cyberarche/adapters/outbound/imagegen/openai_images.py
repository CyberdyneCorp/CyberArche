"""ImageGenerationPort adapter for the OpenAI images API (gpt-image-1 / DALL·E).

Hits `POST {base}/images/generations` and decodes the returned base64 image.
Reuses the same base_url/api_key seam as the OpenAI-compatible LLM adapter.
"""

from __future__ import annotations

import base64

import httpx

from cyberarche.application.ports.images import GeneratedImage

_DEFAULT_BASE = "https://api.openai.com/v1"


class OpenAIImageGenerator:
    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        api_key: str,
        model: str = "gpt-image-1",
        base_url: str = "",
    ) -> None:
        self._http = http
        self._api_key = api_key
        self._model = model
        self._base = (base_url or _DEFAULT_BASE).rstrip("/")

    async def generate(self, prompt: str, *, size: str = "1024x1024") -> GeneratedImage:
        response = await self._http.post(
            f"{self._base}/images/generations",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={"model": self._model, "prompt": prompt, "size": size, "n": 1},
        )
        response.raise_for_status()
        payload = response.json()
        item = payload["data"][0]
        # gpt-image-1 always returns base64; dall-e can return a URL if asked, but
        # we request the default (b64_json) so images never leave via a third URL.
        b64 = item.get("b64_json")
        if not b64:
            raise ValueError("image response had no base64 payload")
        return GeneratedImage(content=base64.b64decode(b64), content_type="image/png")
