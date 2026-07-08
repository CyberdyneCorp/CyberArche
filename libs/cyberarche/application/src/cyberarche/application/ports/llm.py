"""LLM port (ai-agent spec): provider-agnostic chat with normalized tool-calling.

Adapters normalize each provider's tool-call format to ToolCall/ToolResult,
so use cases never see vendor payloads. Provider selection is configuration
(architecture-quality spec): "anthropic" or any OpenAI-compatible endpoint
(OpenAI itself, Ollama, vLLM, ...).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema


@dataclass(frozen=True, slots=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ToolResult:
    call_id: str
    content: str


@dataclass(frozen=True, slots=True)
class LLMMessage:
    role: Literal["system", "user", "assistant", "tool"]
    content: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    tool_result: ToolResult | None = None


@dataclass(frozen=True, slots=True)
class LLMResponse:
    text: str
    tool_calls: tuple[ToolCall, ...] = ()
    model: str = ""

    @property
    def wants_tools(self) -> bool:
        return bool(self.tool_calls)


@dataclass(frozen=True, slots=True)
class LLMConfig:
    provider: str = "anthropic"
    model: str = "claude-sonnet-5"
    api_key: str = ""
    base_url: str = ""  # OpenAI-compatible endpoint (empty = provider default)
    max_tokens: int = 4096


class LLMPort(Protocol):
    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        tools: list[ToolSpec] | None = None,
    ) -> LLMResponse: ...
