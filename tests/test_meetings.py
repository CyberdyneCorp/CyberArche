"""Cyberflies meetings adapter: recordings list/detail and cross-meeting Q&A."""

from __future__ import annotations

import json

import httpx
import pytest

from cyberarche.adapters.outbound.meetings.cyberflies import (
    CyberfliesMeetingsAdapter,
)

BASE_URL = "https://flies.test"


def adapter_with(handler) -> CyberfliesMeetingsAdapter:
    return CyberfliesMeetingsAdapter(
        BASE_URL, httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )


# --- list_recordings ---------------------------------------------------------


async def test_list_recordings_maps_items_and_sends_bearer():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/recordings"
        assert request.headers["Authorization"] == "Bearer tok-1"
        assert request.url.params["limit"] == "20"
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "rec-1",
                        "status": "done",
                        "captured_at": "2026-07-01T10:00:00Z",
                        "summary": {"headline": "Weekly sync"},
                    }
                ]
            },
        )

    recordings = await adapter_with(handler).list_recordings("tok-1")
    assert len(recordings) == 1
    rec = recordings[0]
    assert rec.id == "rec-1"
    assert rec.status == "done"
    assert rec.captured_at == "2026-07-01T10:00:00Z"
    assert rec.headline == "Weekly sync"


async def test_list_recordings_clamps_limit_to_at_most_100():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["limit"] == "100"
        return httpx.Response(200, json={"items": []})

    assert await adapter_with(handler).list_recordings("t", limit=500) == []


async def test_list_recordings_clamps_limit_to_at_least_1():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["limit"] == "1"
        return httpx.Response(200, json={"items": []})

    assert await adapter_with(handler).list_recordings("t", limit=0) == []


async def test_list_recordings_skips_non_dict_items():
    handler = lambda request: httpx.Response(  # noqa: E731
        200, json={"items": ["junk", 42, None, {"id": "rec-2", "status": "done"}]}
    )
    recordings = await adapter_with(handler).list_recordings("t")
    assert [r.id for r in recordings] == ["rec-2"]


async def test_list_recordings_tolerates_missing_items_key():
    handler = lambda request: httpx.Response(200, json={})  # noqa: E731
    assert await adapter_with(handler).list_recordings("t") == []


async def test_list_recordings_falls_back_to_created_at():
    handler = lambda request: httpx.Response(  # noqa: E731
        200,
        json={
            "items": [
                {"id": "r", "status": "done", "created_at": "2026-06-30T09:00:00Z"}
            ]
        },
    )
    (rec,) = await adapter_with(handler).list_recordings("t")
    assert rec.captured_at == "2026-06-30T09:00:00Z"


async def test_list_recordings_ignores_non_dict_summary():
    handler = lambda request: httpx.Response(  # noqa: E731
        200, json={"items": [{"id": "r", "status": "done", "summary": "not-a-dict"}]}
    )
    (rec,) = await adapter_with(handler).list_recordings("t")
    assert rec.headline is None
    assert rec.captured_at is None


async def test_list_recordings_defaults_missing_id_and_status_to_empty():
    handler = lambda request: httpx.Response(200, json={"items": [{}]})  # noqa: E731
    (rec,) = await adapter_with(handler).list_recordings("t")
    assert (rec.id, rec.status, rec.captured_at, rec.headline) == ("", "", None, None)


async def test_list_recordings_raises_on_auth_failure():
    handler = lambda request: httpx.Response(401, json={"detail": "nope"})  # noqa: E731
    with pytest.raises(httpx.HTTPStatusError):
        await adapter_with(handler).list_recordings("bad-token")


async def test_base_url_trailing_slash_is_stripped():
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith(f"{BASE_URL}/api/v1/recordings")
        return httpx.Response(200, json={"items": []})

    adapter = CyberfliesMeetingsAdapter(
        BASE_URL + "/", httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    assert await adapter.list_recordings("t") == []


# --- get_recording -----------------------------------------------------------


async def test_get_recording_maps_full_transcript():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/recordings/rec-9"
        assert request.headers["Authorization"] == "Bearer tok-9"
        return httpx.Response(
            200,
            json={
                "id": "rec-9",
                "status": "done",
                "captured_at": "2026-07-02T15:00:00Z",
                "summary": {
                    "headline": "Planning",
                    "abstract": "We planned things.",
                    "bullets": ["  first  ", "second", "   ", ""],
                    "action_items": [
                        {"text": "  ship it  "},
                        {"text": ""},
                        {"no_text": True},
                        "not-a-dict",
                        {"text": "review PR"},
                    ],
                },
                "transcription": {"text": "hello world"},
            },
        )

    rec = await adapter_with(handler).get_recording("tok-9", "rec-9")
    assert rec.id == "rec-9"
    assert rec.status == "done"
    assert rec.captured_at == "2026-07-02T15:00:00Z"
    assert rec.headline == "Planning"
    assert rec.abstract == "We planned things."
    assert rec.bullets == ["first", "second"]
    assert rec.action_items == ["ship it", "review PR"]
    assert rec.transcript == "hello world"


async def test_get_recording_tolerates_missing_summary_and_transcription():
    handler = lambda request: httpx.Response(  # noqa: E731
        200, json={"id": "rec-0", "status": "processing"}
    )
    rec = await adapter_with(handler).get_recording("t", "rec-0")
    assert rec.headline is None
    assert rec.abstract is None
    assert rec.bullets == []
    assert rec.action_items == []
    assert rec.transcript is None
    assert rec.captured_at is None


async def test_get_recording_ignores_non_dict_summary_and_transcription():
    handler = lambda request: httpx.Response(  # noqa: E731
        200,
        json={
            "id": "rec-0",
            "status": "done",
            "created_at": "2026-06-01T00:00:00Z",
            "summary": ["wrong shape"],
            "transcription": "wrong shape",
        },
    )
    rec = await adapter_with(handler).get_recording("t", "rec-0")
    assert rec.captured_at == "2026-06-01T00:00:00Z"
    assert rec.headline is None
    assert rec.transcript is None


async def test_get_recording_raises_on_not_found():
    handler = lambda request: httpx.Response(404, json={"detail": "gone"})  # noqa: E731
    with pytest.raises(httpx.HTTPStatusError):
        await adapter_with(handler).get_recording("t", "missing")


async def test_get_recording_raises_on_forbidden():
    handler = lambda request: httpx.Response(403, json={"detail": "no"})  # noqa: E731
    with pytest.raises(httpx.HTTPStatusError):
        await adapter_with(handler).get_recording("t", "someone-elses")


# --- ask ---------------------------------------------------------------------


async def test_ask_posts_question_and_returns_trimmed_reply():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/chat"
        assert request.headers["Authorization"] == "Bearer tok-a"
        body = json.loads(request.content)
        assert body == {"messages": [{"role": "user", "content": "what changed?"}]}
        return httpx.Response(200, json={"reply": "  we shipped it  "})

    answer = await adapter_with(handler).ask("tok-a", "what changed?")
    assert answer == "we shipped it"


async def test_ask_without_reply_returns_placeholder():
    handler = lambda request: httpx.Response(200, json={})  # noqa: E731
    assert await adapter_with(handler).ask("t", "q") == "(no answer)"


async def test_ask_with_empty_reply_returns_placeholder():
    handler = lambda request: httpx.Response(200, json={"reply": ""})  # noqa: E731
    assert await adapter_with(handler).ask("t", "q") == "(no answer)"


async def test_ask_raises_on_server_error():
    handler = lambda request: httpx.Response(500, json={"detail": "boom"})  # noqa: E731
    with pytest.raises(httpx.HTTPStatusError):
        await adapter_with(handler).ask("t", "q")
