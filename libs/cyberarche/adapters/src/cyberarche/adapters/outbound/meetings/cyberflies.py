"""MeetingsPort adapter for Cyberflies (meeting transcription).

See the service OpenAPI: GET /api/v1/recordings (list), GET
/api/v1/recordings/{id} (transcript + summary), POST /api/v1/chat (Q&A across
the user's meetings). Cyberflies shares CyberArche's CyberAuth identity and its
API is per-user, so every call carries the *caller's own* access token as the
bearer — Cyberflies enforces access. The token is never logged or stored.
"""

from __future__ import annotations

from typing import Any

import httpx

from cyberarche.application.ports.meetings import (
    MeetingSummary,
    MeetingTranscript,
)


class CyberfliesMeetingsAdapter:
    def __init__(self, base_url: str, http: httpx.AsyncClient) -> None:
        self._base = base_url.rstrip("/")
        self._http = http

    @staticmethod
    def _auth(access_token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {access_token}"}

    async def list_recordings(
        self, access_token: str, *, limit: int = 20
    ) -> list[MeetingSummary]:
        resp = await self._http.get(
            f"{self._base}/api/v1/recordings",
            params={"limit": max(1, min(limit, 100))},
            headers=self._auth(access_token),
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        return [_summary(item) for item in items if isinstance(item, dict)]

    async def get_recording(
        self, access_token: str, recording_id: str
    ) -> MeetingTranscript:
        resp = await self._http.get(
            f"{self._base}/api/v1/recordings/{recording_id}",
            headers=self._auth(access_token),
        )
        resp.raise_for_status()
        return _transcript(resp.json())

    async def ask(self, access_token: str, question: str) -> str:
        resp = await self._http.post(
            f"{self._base}/api/v1/chat",
            json={"messages": [{"role": "user", "content": question}]},
            headers=self._auth(access_token),
        )
        resp.raise_for_status()
        reply = resp.json().get("reply")
        return str(reply).strip() if reply else "(no answer)"


def _summary(item: dict[str, Any]) -> MeetingSummary:
    summary = item.get("summary") or {}
    return MeetingSummary(
        id=str(item.get("id", "")),
        status=str(item.get("status", "")),
        captured_at=item.get("captured_at") or item.get("created_at"),
        headline=(summary.get("headline") if isinstance(summary, dict) else None),
    )


def _transcript(rec: dict[str, Any]) -> MeetingTranscript:
    summary = rec.get("summary") if isinstance(rec.get("summary"), dict) else {}
    transcription = (
        rec.get("transcription") if isinstance(rec.get("transcription"), dict) else {}
    )
    action_items = [
        str(a.get("text", "")).strip()
        for a in (summary.get("action_items") or [])
        if isinstance(a, dict) and a.get("text")
    ]
    bullets = [str(b).strip() for b in (summary.get("bullets") or []) if str(b).strip()]
    return MeetingTranscript(
        id=str(rec.get("id", "")),
        status=str(rec.get("status", "")),
        captured_at=rec.get("captured_at") or rec.get("created_at"),
        headline=summary.get("headline"),
        abstract=summary.get("abstract"),
        bullets=bullets,
        action_items=action_items,
        transcript=(transcription.get("text") if transcription else None),
    )
