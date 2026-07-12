"""Web search + YouTube media port (ai-agent spec): reach the live internet and
YouTube through the sibling DAO backend.

These are interactive, per-caller tools. CyberdyneAuth has no delegation grant,
so every call carries the caller's own access token as a delegation credential —
the adapter forwards it to the DAO backend, which validates it and scopes the
results. Use cases stay provider-agnostic; the token is never logged or stored.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class SearchResult:
    """One ranked web/internet search result."""

    title: str
    url: str
    snippet: str | None = None


@dataclass(frozen=True, slots=True)
class Transcript:
    """One YouTube video's transcript."""

    video_id: str
    text: str
    title: str | None = None
    lang: str | None = None
    url: str | None = None


@dataclass(frozen=True, slots=True)
class PlaylistVideo:
    """One video in a YouTube playlist."""

    video_id: str
    url: str
    title: str | None = None


class WebMediaPort(Protocol):
    async def search(
        self, access_token: str, query: str, *, num: int = 10
    ) -> list[SearchResult]:
        """Ranked web results for `query`. Raises only on transport/auth failure
        (the adapter maps HTTP 401/403 to a clear error)."""
        ...

    async def youtube_transcript(
        self, access_token: str, video: str, *, lang: str | None = None
    ) -> Transcript:
        """A video's transcript (`video` = URL or 11-char id). Raises if the
        video is not found or has no transcript."""
        ...

    async def youtube_playlist(
        self, access_token: str, playlist: str
    ) -> list[PlaylistVideo]:
        """The videos in a playlist (`playlist` = URL or id)."""
        ...
