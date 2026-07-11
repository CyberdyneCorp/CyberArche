"""LLM adapters: tool-calling normalized identically across providers."""

from __future__ import annotations

import json

import httpx

from cyberarche.adapters.outbound.llm.anthropic import AnthropicLLM
from cyberarche.adapters.outbound.llm.openai_compatible import OpenAICompatibleLLM
from cyberarche.application.ports.llm import (
    LLMConfig,
    LLMMessage,
    ToolCall,
    ToolResult,
    ToolSpec,
)

TOOL = ToolSpec(
    name="rag_query",
    description="search",
    parameters={"type": "object", "properties": {"query": {"type": "string"}}},
)

HISTORY = [
    LLMMessage(role="system", content="be helpful"),
    LLMMessage(role="user", content="find the spec"),
    LLMMessage(
        role="assistant",
        tool_calls=(ToolCall(id="c1", name="rag_query", arguments={"query": "spec"}),),
    ),
    LLMMessage(role="tool", tool_result=ToolResult(call_id="c1", content="found it")),
]


def capture(handler):
    seen = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.read())
        seen["headers"] = dict(request.headers)
        return handler(request)

    return _handler, seen


async def test_anthropic_maps_history_and_normalizes_tool_use():
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "claude-sonnet-5",
                "content": [
                    {"type": "text", "text": "checking"},
                    {"type": "tool_use", "id": "c2", "name": "rag_query",
                     "input": {"query": "more"}},
                ],
            },
        )

    handler, seen = capture(respond)
    llm = AnthropicLLM(
        LLMConfig(model="claude-sonnet-5", api_key="k"),
        httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    response = await llm.complete(HISTORY, tools=[TOOL])

    body = seen["body"]
    assert body["system"] == "be helpful"
    assert body["tools"][0]["input_schema"] == TOOL.parameters
    assert body["messages"][1]["content"][0]["type"] == "tool_use"
    assert body["messages"][2]["content"][0]["type"] == "tool_result"
    assert seen["headers"]["x-api-key"] == "k"

    assert response.text == "checking"
    assert response.tool_calls == (
        ToolCall(id="c2", name="rag_query", arguments={"query": "more"}),
    )


async def test_openai_compatible_maps_history_and_normalizes_tool_calls():
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "gpt-test",
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "c2",
                                    "type": "function",
                                    "function": {
                                        "name": "rag_query",
                                        "arguments": '{"query": "more"}',
                                    },
                                }
                            ],
                        }
                    }
                ],
            },
        )

    handler, seen = capture(respond)
    llm = OpenAICompatibleLLM(
        LLMConfig(provider="local", model="gpt-test", base_url="http://llm.local/v1"),
        httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    response = await llm.complete(HISTORY, tools=[TOOL])

    body = seen["body"]
    assert body["messages"][0] == {"role": "system", "content": "be helpful"}
    assert body["messages"][2]["tool_calls"][0]["function"]["name"] == "rag_query"
    assert body["messages"][3]["role"] == "tool"
    assert body["tools"][0]["function"]["parameters"] == TOOL.parameters

    # Same normalized shape as the Anthropic adapter.
    assert response.tool_calls == (
        ToolCall(id="c2", name="rag_query", arguments={"query": "more"}),
    )


def _ok_response(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200, json={"model": "m", "choices": [{"message": {"content": "hi"}}]}
    )


async def test_openai_uses_max_completion_tokens_not_legacy_max_tokens():
    handler, seen = capture(_ok_response)
    llm = OpenAICompatibleLLM(
        LLMConfig(model="gpt-4.1-mini", api_key="k", max_tokens=1234),
        httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    await llm.complete([LLMMessage(role="user", content="hi")])

    body = seen["body"]
    # Forward-compatible: reasoning models reject `max_tokens`.
    assert body["max_completion_tokens"] == 1234
    assert "max_tokens" not in body


async def test_openai_sends_reasoning_effort_only_for_reasoning_models():
    # gpt-5 model → effort is passed through.
    handler, seen = capture(_ok_response)
    gpt5 = OpenAICompatibleLLM(
        LLMConfig(model="gpt-5-mini", api_key="k"),
        httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    await gpt5.complete([LLMMessage(role="user", content="hi")], reasoning_effort="medium")
    assert seen["body"]["reasoning_effort"] == "medium"

    # Non-reasoning model → the field is omitted (sending it 400s on gpt-4.1).
    handler2, seen2 = capture(_ok_response)
    gpt41 = OpenAICompatibleLLM(
        LLMConfig(model="gpt-4.1-mini", api_key="k"),
        httpx.AsyncClient(transport=httpx.MockTransport(handler2)),
    )
    await gpt41.complete([LLMMessage(role="user", content="hi")], reasoning_effort="medium")
    assert "reasoning_effort" not in seen2["body"]
