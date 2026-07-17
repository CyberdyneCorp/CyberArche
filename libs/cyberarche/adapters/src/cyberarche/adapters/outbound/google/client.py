"""GoogleWorkspacePort adapter over Google's REST APIs (OAuth2 + Gmail/Calendar/
Drive/Docs). Enabled only when OAuth client credentials are configured. Tokens
flow through the use case (which encrypts them); this client never stores or logs
a token.
"""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx

from cyberarche.application.ports.google_workspace import GoogleTokens
from cyberarche.domain.google_workspace import (
    BusyPeriod,
    CalendarEvent,
    DriveFile,
    GmailMessage,
    map_doc_elements,
)

_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN = "https://oauth2.googleapis.com/token"
_REVOKE = "https://oauth2.googleapis.com/revoke"


class GoogleWorkspaceClient:
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        http: httpx.AsyncClient,
    ) -> None:
        self._id = client_id
        self._secret = client_secret
        self._redirect = redirect_uri
        self._http = http

    @staticmethod
    def _auth(access_token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {access_token}"}

    # ---- OAuth -------------------------------------------------------------

    def consent_url(self, *, state: str, scopes: list[str]) -> str:
        params = {
            "client_id": self._id,
            "redirect_uri": self._redirect,
            "response_type": "code",
            "scope": " ".join(scopes),
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "state": state,
        }
        return f"{_AUTH}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> GoogleTokens:
        resp = await self._http.post(
            _TOKEN,
            data={
                "code": code,
                "client_id": self._id,
                "client_secret": self._secret,
                "redirect_uri": self._redirect,
                "grant_type": "authorization_code",
            },
        )
        resp.raise_for_status()
        return self._tokens(resp.json(), refresh_fallback="")

    async def refresh(self, refresh_token: str) -> GoogleTokens:
        resp = await self._http.post(
            _TOKEN,
            data={
                "refresh_token": refresh_token,
                "client_id": self._id,
                "client_secret": self._secret,
                "grant_type": "refresh_token",
            },
        )
        resp.raise_for_status()
        # Google usually omits a new refresh token on refresh — keep the old one.
        return self._tokens(resp.json(), refresh_fallback=refresh_token)

    async def revoke(self, token: str) -> None:
        try:
            await self._http.post(_REVOKE, data={"token": token})
        except Exception:
            pass  # best-effort

    def _tokens(self, body: dict[str, Any], *, refresh_fallback: str) -> GoogleTokens:
        expires_in = int(body.get("expires_in", 3600))
        return GoogleTokens(
            access_token=body["access_token"],
            refresh_token=body.get("refresh_token") or refresh_fallback,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
            scopes=str(body.get("scope", "")).split(),
            email=body.get("email", ""),
        )

    # ---- Gmail -------------------------------------------------------------

    async def gmail_search(
        self, access_token: str, query: str, *, limit: int = 10
    ) -> list[GmailMessage]:
        resp = await self._http.get(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages",
            params={"q": query, "maxResults": max(1, min(limit, 25))},
            headers=self._auth(access_token),
        )
        resp.raise_for_status()
        ids = [m["id"] for m in resp.json().get("messages", [])]
        return [await self.gmail_read(access_token, mid) for mid in ids[:limit]]

    async def gmail_read(self, access_token: str, message_id: str) -> GmailMessage:
        resp = await self._http.get(
            f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}",
            params={"format": "full"},
            headers=self._auth(access_token),
        )
        resp.raise_for_status()
        data = resp.json()
        headers = {
            h["name"].lower(): h["value"]
            for h in data.get("payload", {}).get("headers", [])
        }
        return GmailMessage(
            id=data.get("id", message_id),
            thread_id=data.get("threadId", ""),
            subject=headers.get("subject", ""),
            sender=headers.get("from", ""),
            snippet=data.get("snippet", ""),
            body=_gmail_body(data.get("payload", {})),
        )

    # Gmail is read-only — no draft/compose/send (least privilege).

    # ---- Calendar ----------------------------------------------------------

    async def calendar_list(
        self, access_token: str, *, time_min: str, time_max: str
    ) -> list[CalendarEvent]:
        resp = await self._http.get(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            params={
                "timeMin": time_min,
                "timeMax": time_max,
                "singleEvents": "true",
                "orderBy": "startTime",
            },
            headers=self._auth(access_token),
        )
        resp.raise_for_status()
        events = []
        for item in resp.json().get("items", []):
            events.append(
                CalendarEvent(
                    id=item.get("id", ""),
                    summary=item.get("summary", "(no title)"),
                    start=item.get("start", {}).get("dateTime")
                    or item.get("start", {}).get("date", ""),
                    end=item.get("end", {}).get("dateTime")
                    or item.get("end", {}).get("date", ""),
                    attendees=[
                        a.get("email", "") for a in item.get("attendees", [])
                    ],
                )
            )
        return events

    async def calendar_free_busy(
        self, access_token: str, *, time_min: str, time_max: str
    ) -> list[BusyPeriod]:
        resp = await self._http.post(
            "https://www.googleapis.com/calendar/v3/freeBusy",
            json={
                "timeMin": time_min,
                "timeMax": time_max,
                "items": [{"id": "primary"}],
            },
            headers=self._auth(access_token),
        )
        resp.raise_for_status()
        primary = resp.json().get("calendars", {}).get("primary", {})
        return [
            BusyPeriod(start=b["start"], end=b["end"])
            for b in primary.get("busy", [])
        ]

    async def calendar_create_event(
        self,
        access_token: str,
        *,
        summary: str,
        start: str,
        end: str,
        attendees: list[str],
    ) -> str:
        resp = await self._http.post(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            json={
                "summary": summary,
                "start": {"dateTime": start},
                "end": {"dateTime": end},
                "attendees": [{"email": e} for e in attendees],
            },
            headers=self._auth(access_token),
        )
        resp.raise_for_status()
        return resp.json().get("id", "")

    # ---- Drive / Docs ------------------------------------------------------

    async def drive_search(
        self, access_token: str, query: str, *, limit: int = 10
    ) -> list[DriveFile]:
        resp = await self._http.get(
            "https://www.googleapis.com/drive/v3/files",
            params={
                "q": f"name contains '{query}'",
                "pageSize": max(1, min(limit, 25)),
                "fields": "files(id,name,mimeType,webViewLink)",
            },
            headers=self._auth(access_token),
        )
        resp.raise_for_status()
        return [
            DriveFile(
                id=f.get("id", ""),
                name=f.get("name", ""),
                mime_type=f.get("mimeType", ""),
                web_link=f.get("webViewLink", ""),
            )
            for f in resp.json().get("files", [])
        ]

    async def import_doc(self, access_token: str, doc_id: str) -> list[dict]:
        resp = await self._http.get(
            f"https://docs.googleapis.com/v1/documents/{doc_id}",
            headers=self._auth(access_token),
        )
        resp.raise_for_status()
        return map_doc_elements(_doc_elements(resp.json()))

    # ---- Sheets / Slides (read-only) ---------------------------------------

    async def sheets_read(
        self, access_token: str, spreadsheet_id: str, *, range: str = ""
    ) -> str:
        cell_range = range or "A1:Z100"
        resp = await self._http.get(
            f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}"
            f"/values/{cell_range}",
            headers=self._auth(access_token),
        )
        resp.raise_for_status()
        rows = resp.json().get("values", [])
        return "\n".join("\t".join(str(cell) for cell in row) for row in rows)

    async def slides_read(self, access_token: str, presentation_id: str) -> str:
        resp = await self._http.get(
            f"https://slides.googleapis.com/v1/presentations/{presentation_id}",
            headers=self._auth(access_token),
        )
        resp.raise_for_status()
        return _slide_text(resp.json())


def _gmail_body(payload: dict[str, Any]) -> str:
    """Best-effort plain-text body from a Gmail payload."""
    for part in [payload, *payload.get("parts", [])]:
        if part.get("mimeType") == "text/plain":
            data = part.get("body", {}).get("data")
            if data:
                return base64.urlsafe_b64decode(data + "===").decode(
                    "utf-8", "replace"
                )
    return payload.get("snippet", "")


def _doc_elements(doc: dict[str, Any]) -> list[dict]:
    """Flatten a Google Doc's body into simplified {type, text, level} elements."""
    elements: list[dict] = []
    for item in doc.get("body", {}).get("content", []):
        para = item.get("paragraph")
        if not para:
            continue
        text = "".join(
            el.get("textRun", {}).get("content", "") for el in para.get("elements", [])
        ).strip()
        if not text:
            continue
        style = para.get("paragraphStyle", {}).get("namedStyleType", "")
        if style.startswith("HEADING_"):
            level = int(style.rsplit("_", 1)[-1] or 2)
            elements.append({"type": "heading", "text": text, "level": level})
        elif para.get("bullet") is not None:
            elements.append({"type": "bulleted_list", "text": text})
        else:
            elements.append({"type": "paragraph", "text": text})
    return elements


def _slide_text(presentation: dict[str, Any]) -> str:
    """Flatten a Slides presentation into per-slide text lines (read-only)."""
    lines: list[str] = []
    for index, slide in enumerate(presentation.get("slides", []), start=1):
        texts: list[str] = []
        for element in slide.get("pageElements", []):
            shape = element.get("shape", {})
            for run in shape.get("text", {}).get("textElements", []):
                content = run.get("textRun", {}).get("content", "").strip()
                if content:
                    texts.append(content)
        if texts:
            lines.append(f"Slide {index}: " + " ".join(texts))
    return "\n".join(lines)
