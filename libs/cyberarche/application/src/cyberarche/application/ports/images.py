"""Image-generation port (ai-agent spec): text-to-image, provider-agnostic.

The agent uses this to create an image from a prompt; the adapter decides the
provider (OpenAI gpt-image-1 by default). Kept separate from LLMPort because it
is a different capability with a different API surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class GeneratedImage:
    content: bytes
    content_type: str


class ImageGenerationPort(Protocol):
    async def generate(self, prompt: str, *, size: str = "1024x1024") -> GeneratedImage:
        """Create an image from a text prompt. Raises on provider failure."""
        ...
