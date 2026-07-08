"""LLMPort adapter for OpenAI-compatible chat APIs.

Covers OpenAI itself and any compatible local runtime (Ollama, vLLM,
llama.cpp server) via `base_url` — the "local" provider option.
"""

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

_DEFAULT_BASE = "https://api.openai.com/v1"


def _to_openai_messages(messages: list[LLMMessage]) -> list[dict]:
    result: list[dict[str, Any]] = []
    for message in messages:
        if message.role == "assistant" and message.tool_calls:
            result.append(
                {
                    "role": "assistant",
                    "content": message.content or None,
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {
                                "name": call.name,
                                "arguments": json.dumps(call.arguments),
                            },
                        }
                        for call in message.tool_calls
                    ],
                }
            )
        elif message.role == "tool" and message.tool_result:
            result.append(
                {
                    "role": "tool",
                    "tool_call_id": message.tool_result.call_id,
                    "content": message.tool_result.content,
                }
            )
        else:
            result.append({"role": message.role, "content": message.content})
    return result


class OpenAICompatibleLLM:
    def __init__(self, config: LLMConfig, http: httpx.AsyncClient) -> None:
        self._config = config
        self._http = http
        self._base = (config.base_url or _DEFAULT_BASE).rstrip("/")

    async def complete(
        self, messages: list[LLMMessage], *, tools: list[ToolSpec] | None = None
    ) -> LLMResponse:
        body: dict[str, Any] = {
            "model": self._config.model,
            "max_tokens": self._config.max_tokens,
            "messages": _to_openai_messages(messages),
        }
        if tools:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
                for tool in tools
            ]
        headers = {}
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"
        response = await self._http.post(
            f"{self._base}/chat/completions", json=body, headers=headers
        )
        response.raise_for_status()
        return _from_openai(response.json())


def _from_openai(payload: dict) -> LLMResponse:
    message = payload["choices"][0]["message"]
    calls = tuple(
        ToolCall(
            id=call["id"],
            name=call["function"]["name"],
            arguments=json.loads(call["function"].get("arguments") or "{}"),
        )
        for call in message.get("tool_calls") or []
    )
    return LLMResponse(
        text=message.get("content") or "",
        tool_calls=calls,
        model=payload.get("model", ""),
    )
