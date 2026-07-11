"""Meeting-transcript port (ai-agent spec): read the caller's meeting recordings
and transcripts, and answer questions across them.

The data is strictly per-user, so every call carries the caller's own access
token as a delegation credential — the adapter presents it to the provider
(Cyberflies), which enforces access. Use cases stay provider-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class MeetingSummary:
    """A recording in a list: enough to identify and pick one."""

    id: str
    status: str
    captured_at: str | None
    headline: str | None


@dataclass(frozen=True, slots=True)
class MeetingTranscript:
    """One recording's full transcript + summary."""

    id: str
    status: str
    captured_at: str | None
    headline: str | None
    abstract: str | None
    bullets: list[str] = field(default_factory=list)
    action_items: list[str] = field(default_factory=list)
    transcript: str | None = None


class MeetingsPort(Protocol):
    async def list_recordings(
        self, access_token: str, *, limit: int = 20
    ) -> list[MeetingSummary]:
        """Recent recordings the caller can see. Raises only on transport/auth
        failure (the adapter maps HTTP 401/403 to a clear error)."""
        ...

    async def get_recording(
        self, access_token: str, recording_id: str
    ) -> MeetingTranscript:
        """One recording's transcript + summary. Raises if not found/forbidden."""
        ...

    async def ask(self, access_token: str, question: str) -> str:
        """Answer a natural-language question across the caller's meetings."""
        ...
