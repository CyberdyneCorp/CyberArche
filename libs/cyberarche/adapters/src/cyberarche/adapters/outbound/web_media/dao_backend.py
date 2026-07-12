"""WebMediaPort adapter for the Cyberdyne DAO backend (web search + YouTube).

See the DAO OpenAPI: GET /api/v1/search (web search), GET
/api/v1/youtube/transcript (a video's transcript), GET /api/v1/youtube/playlist
(a playlist's videos). The DAO backend shares CyberArche's CyberdyneAuth
identity, so every call carries the *caller's own* access token as the bearer —
the DAO backend enforces access. The token is never logged or stored.
"""

from __future__ import annotations

from typing import Any

import httpx

from cyberarche.application.ports.web_media import (
    PlaylistVideo,
    SearchResult,
    Transcript,
)


class DaoBackendWebMediaAdapter:
    def __init__(self, base_url: str, http: httpx.AsyncClient) -> None:
        self._base = base_url.rstrip("/")
        self._http = http

    @staticmethod
    def _auth(access_token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {access_token}"}

    async def search(
        self, access_token: str, query: str, *, num: int = 10
    ) -> list[SearchResult]:
        resp = await self._http.get(
            f"{self._base}/api/v1/search",
            params={"q": query, "num": max(1, min(num, 20))},
            headers=self._auth(access_token),
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        return [_result(r) for r in results if isinstance(r, dict)]

    async def youtube_transcript(
        self, access_token: str, video: str, *, lang: str | None = None
    ) -> Transcript:
        params: dict[str, str] = {"video": video}
        if lang:
            params["lang"] = lang
        resp = await self._http.get(
            f"{self._base}/api/v1/youtube/transcript",
            params=params,
            headers=self._auth(access_token),
        )
        resp.raise_for_status()
        return _transcript(resp.json())

    async def youtube_playlist(
        self, access_token: str, playlist: str
    ) -> list[PlaylistVideo]:
        resp = await self._http.get(
            f"{self._base}/api/v1/youtube/playlist",
            params={"playlist": playlist},
            headers=self._auth(access_token),
        )
        resp.raise_for_status()
        videos = resp.json().get("videos", [])
        return [_video(v) for v in videos if isinstance(v, dict)]


def _result(item: dict[str, Any]) -> SearchResult:
    return SearchResult(
        title=str(item.get("title", "")),
        url=str(item.get("url", "")),
        snippet=(item.get("snippet") or None),
    )


def _transcript(rec: dict[str, Any]) -> Transcript:
    return Transcript(
        video_id=str(rec.get("videoId", "")),
        text=str(rec.get("text", "")),
        title=rec.get("title"),
        lang=rec.get("language"),
        url=rec.get("url"),
    )


def _video(item: dict[str, Any]) -> PlaylistVideo:
    return PlaylistVideo(
        video_id=str(item.get("videoId", "")),
        url=str(item.get("url", "")),
        title=item.get("title"),
    )
