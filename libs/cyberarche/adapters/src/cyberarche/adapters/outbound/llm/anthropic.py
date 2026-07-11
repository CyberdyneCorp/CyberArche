"""LLMPort adapter for the Anthropic Messages API (tool use normalized)."""

from __future__ import annotations

import json
from typing import Any

import httpx

from cyberarche.application.ports.llm import (
    LLMConfig,
    LLMMessage,
    LLMResponse,
    ToolCall,
    ToolSpec,
)

_DEFAULT_BASE = "https://api.anthropic.com"
_API_VERSION = "2023-06-01"


def _to_anthropic_messages(messages: list[LLMMessage]) -> tuple[str, list[dict]]:
    """Split the system prompt out and map our normalized history."""
    system = ""
    result: list[dict] = []
    for message in messages:
        if message.role == "system":
            system = message.content
        elif message.role == "assistant" and message.tool_calls:
            content: list[dict[str, Any]] = []
            if message.content:
                content.append({"type": "text", "text": message.content})
            content.extend(
                {
                    "type": "tool_use",
                    "id": call.id,
                    "name": call.name,
                    "input": call.arguments,
                }
                for call in message.tool_calls
            )
            result.append({"role": "assistant", "content": content})
        elif message.role == "tool" and message.tool_result:
            result.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": message.tool_result.call_id,
                            "content": message.tool_result.content,
                        }
                    ],
                }
            )
        else:
            result.append({"role": message.role, "content": message.content})
    return system, result


class AnthropicLLM:
    def __init__(self, config: LLMConfig, http: httpx.AsyncClient) -> None:
        self._config = config
        self._http = http
        self._base = (config.base_url or _DEFAULT_BASE).rstrip("/")

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        tools: list[ToolSpec] | None = None,
        reasoning_effort: str | None = None,  # noqa: ARG002 — OpenAI-only knob
    ) -> LLMResponse:
        system, mapped = _to_anthropic_messages(messages)
        body: dict[str, Any] = {
            "model": self._config.model,
            "max_tokens": self._config.max_tokens,
            "messages": mapped,
        }
        if system:
            body["system"] = system
        if tools:
            body["tools"] = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.parameters,
                }
                for tool in tools
            ]
        response = await self._http.post(
            f"{self._base}/v1/messages",
            json=body,
            headers={
                "x-api-key": self._config.api_key,
                "anthropic-version": _API_VERSION,
            },
        )
        response.raise_for_status()
        return _from_anthropic(response.json())


def _from_anthropic(payload: dict) -> LLMResponse:
    text_parts: list[str] = []
    calls: list[ToolCall] = []
    for block in payload.get("content", []):
        if block.get("type") == "text":
            text_parts.append(block.get("text", ""))
        elif block.get("type") == "tool_use":
            arguments = block.get("input", {})
            if isinstance(arguments, str):  # defensive: some proxies stringify
                arguments = json.loads(arguments or "{}")
            calls.append(
                ToolCall(id=block["id"], name=block["name"], arguments=arguments)
            )
    return LLMResponse(
        text="\n".join(text_parts),
        tool_calls=tuple(calls),
        model=payload.get("model", ""),
    )
