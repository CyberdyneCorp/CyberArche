"""ImageGenerationPort adapter for the OpenAI images API (gpt-image-1 / DALL·E).

Hits `POST {base}/images/generations` and decodes the returned base64 image.
Reuses the same base_url/api_key seam as the OpenAI-compatible LLM adapter.
"""

from __future__ import annotations

import base64

import httpx

from cyberarche.application.ports.images import GeneratedImage

_DEFAULT_BASE = "https://api.openai.com/v1"
# gpt-image-1 routinely takes 30-60s for a 1024x1024 render, so this call needs
# its own budget — the shared client's 30s default was cutting generations off
# mid-flight (surfaced to the agent as a bare "error:").
_IMAGE_TIMEOUT_S = 120.0


class OpenAIImageGenerator:
    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        api_key: str,
        model: str = "gpt-image-1",
        base_url: str = "",
        timeout: float = _IMAGE_TIMEOUT_S,
    ) -> None:
        self._http = http
        self._api_key = api_key
        self._model = model
        self._base = (base_url or _DEFAULT_BASE).rstrip("/")
        self._timeout = timeout

    async def generate(self, prompt: str, *, size: str = "1024x1024") -> GeneratedImage:
        response = await self._http.post(
            f"{self._base}/images/generations",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={"model": self._model, "prompt": prompt, "size": size, "n": 1},
            timeout=self._timeout,
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            # Surface the provider's reason (content policy, quota, verification…)
            # instead of a generic status so the agent can explain the failure.
            raise RuntimeError(_provider_error(response)) from error
        payload = response.json()
        item = payload["data"][0]
        # gpt-image-1 always returns base64; dall-e can return a URL if asked, but
        # we request the default (b64_json) so images never leave via a third URL.
        b64 = item.get("b64_json")
        if not b64:
            raise ValueError("image response had no base64 payload")
        return GeneratedImage(content=base64.b64decode(b64), content_type="image/png")


def _provider_error(response: httpx.Response) -> str:
    """The OpenAI error message, or a compact fallback."""
    try:
        message = response.json().get("error", {}).get("message")
        if message:
            return str(message)
    except (ValueError, AttributeError):
        pass
    return f"image provider returned HTTP {response.status_code}"
