"""Google Workspace connector domain (google-workspace-connector spec).

A `GoogleConnection` is a personal Google account linked to a workspace. The
domain object carries only metadata (status, granted scopes, connected email) —
the OAuth tokens live encrypted in the repository and are never part of this
object. Scope groups map user-consented tool groups to the minimal Google
scopes, and `map_doc_elements` turns a Google Doc's simplified structure into
CyberArche blocks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from cyberarche.domain.ids import (
    GoogleConnectionId,
    TenantId,
    UserId,
    WorkspaceId,
)

# Full Google OAuth scope URLs, grouped by the tool group a user consents to.
_G = "https://www.googleapis.com/auth/"
SCOPE_GROUPS: dict[str, list[str]] = {
    "gmail_read": [f"{_G}gmail.readonly"],
    "gmail_compose": [f"{_G}gmail.compose"],
    "calendar": [f"{_G}calendar"],
    "drive": [f"{_G}drive.readonly", f"{_G}documents.readonly"],
}

# The scope each tool requires before it may call Google.
SCOPE_GMAIL_READ = f"{_G}gmail.readonly"
SCOPE_GMAIL_COMPOSE = f"{_G}gmail.compose"
SCOPE_CALENDAR = f"{_G}calendar"
SCOPE_DRIVE = f"{_G}drive.readonly"
SCOPE_DOCS = f"{_G}documents.readonly"

STATUS_CONNECTED = "connected"
STATUS_NEEDS_RECONNECT = "needs_reconnect"
STATUS_DISCONNECTED = "disconnected"


def scopes_for_groups(groups: list[str]) -> list[str]:
    """The minimal, de-duplicated Google scopes for the consented tool groups."""
    out: dict[str, None] = {}
    for group in groups:
        for scope in SCOPE_GROUPS.get(group, []):
            out.setdefault(scope, None)
    return list(out)


@dataclass(frozen=True, slots=True)
class GoogleConnection:
    """Metadata for a user's Google connection — never carries tokens."""

    id: GoogleConnectionId
    tenant_id: TenantId
    workspace_id: WorkspaceId
    user_id: UserId
    google_email: str
    status: str
    scopes: list[str]
    created_at: datetime
    updated_at: datetime
    token_expires_at: datetime | None = None

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes

    def is_expired(self, now: datetime) -> bool:
        return self.token_expires_at is not None and now >= self.token_expires_at

    def is_usable(self) -> bool:
        return self.status == STATUS_CONNECTED


def map_doc_elements(elements: list[dict]) -> list[dict]:
    """Map a Google Doc's simplified elements to CyberArche block dicts.

    Each element is `{type, text, level?}` where type is
    heading/paragraph/bulleted_list/numbered_list/code; unknown types degrade to
    a paragraph so no content is lost."""
    blocks: list[dict] = []
    for element in elements:
        kind = str(element.get("type", "paragraph"))
        text = str(element.get("text", ""))
        if kind == "heading":
            level = int(element.get("level", 2))
            blocks.append(
                {"type": "heading", "data": {"text": text, "level": max(1, min(level, 4))}}
            )
        elif kind == "code":
            blocks.append(
                {"type": "code", "data": {"source": text, "language": "text"}}
            )
        elif kind in ("bulleted_list", "numbered_list", "quote"):
            blocks.append({"type": kind, "data": {"text": text}})
        else:
            blocks.append({"type": "paragraph", "data": {"text": text}})
    return blocks


@dataclass(frozen=True, slots=True)
class GmailMessage:
    id: str
    thread_id: str
    subject: str
    sender: str
    snippet: str
    body: str = ""


@dataclass(frozen=True, slots=True)
class CalendarEvent:
    id: str
    summary: str
    start: str
    end: str
    attendees: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class BusyPeriod:
    start: str
    end: str


@dataclass(frozen=True, slots=True)
class DriveFile:
    id: str
    name: str
    mime_type: str
    web_link: str = ""
