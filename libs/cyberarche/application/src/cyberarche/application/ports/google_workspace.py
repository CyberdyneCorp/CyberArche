"""Google Workspace ports (google-workspace-connector spec).

`GoogleWorkspacePort` is the outbound boundary to Google: the OAuth2 flow plus
Gmail/Calendar/Drive/Docs REST calls (every API method takes an access token).
`GoogleConnectionRepository` stores connections; it accepts and returns encrypted
token bytes and never plaintext, mirroring the connector credential store.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from cyberarche.domain.google_workspace import (
    BusyPeriod,
    CalendarEvent,
    DriveFile,
    GmailMessage,
    GoogleConnection,
)
from cyberarche.domain.ids import TenantId, UserId, WorkspaceId


@dataclass(frozen=True, slots=True)
class GoogleTokens:
    """The result of an OAuth exchange/refresh — plaintext, used transiently."""

    access_token: str
    refresh_token: str
    expires_at: datetime
    scopes: list[str] = field(default_factory=list)
    email: str = ""


class GoogleWorkspacePort(Protocol):
    # ---- OAuth ----
    def consent_url(self, *, state: str, scopes: list[str]) -> str:
        """The Google consent URL requesting exactly `scopes`."""
        ...

    async def exchange_code(self, code: str) -> GoogleTokens: ...

    async def refresh(self, refresh_token: str) -> GoogleTokens:
        """New access token from the refresh token. Raises on a revoked token."""
        ...

    async def revoke(self, token: str) -> None:
        """Best-effort revoke at Google (never raises for the caller)."""
        ...

    # ---- Gmail ----
    async def gmail_search(
        self, access_token: str, query: str, *, limit: int = 10
    ) -> list[GmailMessage]: ...

    async def gmail_read(
        self, access_token: str, message_id: str
    ) -> GmailMessage: ...

    # Gmail is read-only — no compose/draft/send. (audit: least privilege)

    # ---- Calendar ----
    async def calendar_list(
        self, access_token: str, *, time_min: str, time_max: str
    ) -> list[CalendarEvent]: ...

    async def calendar_free_busy(
        self, access_token: str, *, time_min: str, time_max: str
    ) -> list[BusyPeriod]: ...

    async def calendar_create_event(
        self,
        access_token: str,
        *,
        summary: str,
        start: str,
        end: str,
        attendees: list[str],
    ) -> str:
        """Create an event; returns the event id. Invoked only on explicit user
        action (never as an autonomous agent tool)."""
        ...

    # ---- Drive / Docs ----
    async def drive_search(
        self, access_token: str, query: str, *, limit: int = 10
    ) -> list[DriveFile]: ...

    async def import_doc(self, access_token: str, doc_id: str) -> list[dict]:
        """Fetch a Doc and return CyberArche block dicts (headings/text/…)."""
        ...

    # ---- Sheets / Slides (read-only) ----
    async def sheets_read(
        self, access_token: str, spreadsheet_id: str, *, range: str = ""
    ) -> str:
        """Read a spreadsheet's values as text (optionally an A1 range)."""
        ...

    async def slides_read(self, access_token: str, presentation_id: str) -> str:
        """Read a presentation's slide text."""
        ...


class GoogleConnectionRepository(Protocol):
    async def upsert(
        self,
        connection: GoogleConnection,
        *,
        access_encrypted: bytes,
        refresh_encrypted: bytes,
    ) -> None:
        """Insert or replace the (tenant, workspace, user) connection + tokens."""
        ...

    async def get(
        self, tenant_id: TenantId, workspace_id: WorkspaceId, user_id: UserId
    ) -> GoogleConnection | None:
        """Metadata for the caller's connection, or None. Never returns tokens."""
        ...

    async def read_secrets(
        self, tenant_id: TenantId, workspace_id: WorkspaceId, user_id: UserId
    ) -> tuple[bytes, bytes] | None:
        """The (access_encrypted, refresh_encrypted) bytes for the connection,
        for the use case to decrypt — never exposed outside the application."""
        ...

    async def set_status(
        self,
        tenant_id: TenantId,
        workspace_id: WorkspaceId,
        user_id: UserId,
        status: str,
        updated_at: datetime,
    ) -> None: ...

    async def delete(
        self, tenant_id: TenantId, workspace_id: WorkspaceId, user_id: UserId
    ) -> None: ...
