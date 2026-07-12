"""DaoBackendWebMediaAdapter wire-level behavior against a mocked DAO API."""

from __future__ import annotations

import httpx
import pytest

from cyberarche.adapters.outbound.web_media.dao_backend import (
    DaoBackendWebMediaAdapter,
)

BASE = "https://dao.test"
TOKEN = "caller-access-token"


def adapter_with(handler) -> tuple[DaoBackendWebMediaAdapter, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def recording_handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    http = httpx.AsyncClient(transport=httpx.MockTransport(recording_handler))
    return DaoBackendWebMediaAdapter(BASE, http), seen


async def test_search_forwards_bearer_and_maps_results():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/search"
        assert request.url.params["q"] == "cyberdyne"
        assert request.url.params["num"] == "5"
        return httpx.Response(
            200,
            json={
                "query": "cyberdyne",
                "answer": "an answer",
                "results": [
                    {"position": 1, "title": "T1", "url": "u1", "snippet": "s1"},
                    {"position": 2, "title": "T2", "url": "u2", "snippet": ""},
                ],
            },
        )

    adapter, seen = adapter_with(handler)
    results = await adapter.search(TOKEN, "cyberdyne", num=5)
    assert seen[0].headers["authorization"] == f"Bearer {TOKEN}"
    assert [(r.title, r.url) for r in results] == [("T1", "u1"), ("T2", "u2")]
    assert results[0].snippet == "s1"
    assert results[1].snippet is None  # empty snippet normalized to None


async def test_search_clamps_num_to_bounds():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["num"] == "20"  # clamped from 999
        return httpx.Response(200, json={"results": []})

    adapter, _ = adapter_with(handler)
    assert await adapter.search(TOKEN, "q", num=999) == []


async def test_youtube_transcript_maps_fields_and_lang_param():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/youtube/transcript"
        assert request.url.params["video"] == "abc123"
        assert request.url.params["lang"] == "en"
        return httpx.Response(
            200,
            json={
                "videoId": "abc123",
                "url": "https://youtu.be/abc123",
                "language": "en",
                "text": "hello world",
            },
        )

    adapter, seen = adapter_with(handler)
    t = await adapter.youtube_transcript(TOKEN, "abc123", lang="en")
    assert seen[0].headers["authorization"] == f"Bearer {TOKEN}"
    assert t.video_id == "abc123"
    assert t.text == "hello world"
    assert t.lang == "en"


async def test_youtube_transcript_omits_lang_when_absent():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "lang" not in request.url.params
        return httpx.Response(200, json={"videoId": "x", "text": "t"})

    adapter, _ = adapter_with(handler)
    await adapter.youtube_transcript(TOKEN, "x")


async def test_youtube_playlist_maps_videos():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/youtube/playlist"
        return httpx.Response(
            200,
            json={
                "playlistId": "pl1",
                "title": "My list",
                "videos": [
                    {"videoId": "v1", "url": "uu1", "title": "One"},
                    {"videoId": "v2", "url": "uu2", "title": "Two"},
                ],
            },
        )

    adapter, _ = adapter_with(handler)
    videos = await adapter.youtube_playlist(TOKEN, "pl1")
    assert [(v.video_id, v.url, v.title) for v in videos] == [
        ("v1", "uu1", "One"),
        ("v2", "uu2", "Two"),
    ]


@pytest.mark.parametrize("status", [401, 403, 404, 500])
async def test_http_errors_raise_with_response_attached(status: int):
    # The adapter raises; the agent maps status -> a friendly string. Assert the
    # raised error carries the response (so _web_media_error can read the status).
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"detail": "nope"})

    adapter, _ = adapter_with(handler)
    with pytest.raises(httpx.HTTPStatusError) as exc:
        await adapter.search(TOKEN, "q")
    assert exc.value.response.status_code == status
