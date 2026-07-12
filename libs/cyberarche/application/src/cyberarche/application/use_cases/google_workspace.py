"""Google Workspace connector use cases (google-workspace-connector spec).

Per-user OAuth: `connect` builds a consent URL with a signed state;
`complete_connect` verifies the state and stores encrypted tokens. Every tool
resolves the connection strictly by the CURRENT caller's user id (so one user
can never use another's connection), checks the required scope, and refreshes an
expired access token automatically — flipping the connection to
`needs_reconnect` if the refresh token has been revoked. Send/create are not
agent tools; they run only from an explicit user action (the HTTP router).
"""

from __future__ import annotations

import base64
import json

from cyberarche.application.authz import AccessControl
from cyberarche.application.kernel import CallerContext
from cyberarche.application.ports.google_workspace import (
    GoogleConnectionRepository,
    GoogleWorkspacePort,
)
from cyberarche.application.ports.mcp import SecretBoxPort
from cyberarche.application.ports.telemetry import ClockPort, IdPort
from cyberarche.domain.errors import ValidationFailed
from cyberarche.domain.google_workspace import (
    SCOPE_CALENDAR,
    SCOPE_DOCS,
    SCOPE_DRIVE,
    SCOPE_GMAIL_COMPOSE,
    SCOPE_GMAIL_READ,
    STATUS_CONNECTED,
    STATUS_NEEDS_RECONNECT,
    GoogleConnection,
    scopes_for_groups,
)
from cyberarche.domain.ids import (
    GoogleConnectionId,
    TenantId,
    UserId,
    WorkspaceId,
)
from cyberarche.domain.memberships import Role


class GoogleWorkspaceUseCases:
    def __init__(
        self,
        connections: GoogleConnectionRepository,
        google: GoogleWorkspacePort,
        secret_box: SecretBoxPort,
        access: AccessControl,
        clock: ClockPort,
        ids: IdPort,
    ) -> None:
        self._connections = connections
        self._google = google
        self._secret_box = secret_box
        self._access = access
        self._clock = clock
        self._ids = ids

    # ---- OAuth lifecycle ---------------------------------------------------

    async def connect(
        self, caller: CallerContext, workspace_id: WorkspaceId, groups: list[str]
    ) -> str:
        """Consent URL requesting only the scopes for the chosen tool groups."""
        await self._access.require_workspace(caller, workspace_id, Role.VIEWER)
        scopes = scopes_for_groups(groups)
        if not scopes:
            raise ValidationFailed("choose at least one Google tool group")
        state = self._sign_state(caller, workspace_id)
        return self._google.consent_url(state=state, scopes=scopes)

    async def complete_connect(self, state: str, code: str) -> GoogleConnection:
        """Handle the OAuth callback: verify state, exchange code, store tokens."""
        tenant_id, workspace_id, user_id = self._verify_state(state)
        tokens = await self._google.exchange_code(code)
        now = self._clock.now()
        connection = GoogleConnection(
            id=GoogleConnectionId(self._ids.new_id()),
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            user_id=user_id,
            google_email=tokens.email,
            status=STATUS_CONNECTED,
            scopes=list(tokens.scopes),
            created_at=now,
            updated_at=now,
            token_expires_at=tokens.expires_at,
        )
        await self._connections.upsert(
            connection,
            access_encrypted=self._secret_box.encrypt(tokens.access_token),
            refresh_encrypted=self._secret_box.encrypt(tokens.refresh_token),
        )
        return connection

    async def status(
        self, caller: CallerContext, workspace_id: WorkspaceId
    ) -> GoogleConnection | None:
        await self._access.require_workspace(caller, workspace_id, Role.VIEWER)
        return await self._connections.get(
            caller.tenant_id, workspace_id, caller.user_id
        )

    async def disconnect(
        self, caller: CallerContext, workspace_id: WorkspaceId
    ) -> None:
        await self._access.require_workspace(caller, workspace_id, Role.VIEWER)
        secrets = await self._connections.read_secrets(
            caller.tenant_id, workspace_id, caller.user_id
        )
        if secrets is not None:
            # Best-effort revoke at Google, then remove the stored tokens.
            try:
                await self._google.revoke(self._secret_box.decrypt(secrets[1]))
            except Exception:
                pass
        await self._connections.delete(
            caller.tenant_id, workspace_id, caller.user_id
        )

    # ---- Gmail -------------------------------------------------------------

    async def gmail_search(self, caller, workspace_id, query: str):
        token = await self._token_for(caller, workspace_id, SCOPE_GMAIL_READ)
        return await self._google.gmail_search(token, query)

    async def gmail_read(self, caller, workspace_id, message_id: str):
        token = await self._token_for(caller, workspace_id, SCOPE_GMAIL_READ)
        return await self._google.gmail_read(token, message_id)

    async def gmail_draft(self, caller, workspace_id, *, to, subject, body) -> str:
        token = await self._token_for(caller, workspace_id, SCOPE_GMAIL_COMPOSE)
        return await self._google.gmail_create_draft(
            token, to=to, subject=subject, body=body
        )

    # ---- Calendar ----------------------------------------------------------

    async def calendar_list(self, caller, workspace_id, *, time_min, time_max):
        token = await self._token_for(caller, workspace_id, SCOPE_CALENDAR)
        return await self._google.calendar_list(
            token, time_min=time_min, time_max=time_max
        )

    async def calendar_free_busy(self, caller, workspace_id, *, time_min, time_max):
        token = await self._token_for(caller, workspace_id, SCOPE_CALENDAR)
        return await self._google.calendar_free_busy(
            token, time_min=time_min, time_max=time_max
        )

    async def calendar_create_event(
        self, caller, workspace_id, *, summary, start, end, attendees
    ) -> str:
        """Explicit user action only (HTTP router) — never an agent tool."""
        token = await self._token_for(caller, workspace_id, SCOPE_CALENDAR)
        return await self._google.calendar_create_event(
            token, summary=summary, start=start, end=end, attendees=attendees
        )

    # ---- Drive / Docs ------------------------------------------------------

    async def drive_search(self, caller, workspace_id, query: str):
        token = await self._token_for(caller, workspace_id, SCOPE_DRIVE)
        return await self._google.drive_search(token, query)

    async def import_doc(self, caller, workspace_id, doc_id: str) -> list[dict]:
        token = await self._token_for(caller, workspace_id, SCOPE_DOCS)
        blocks = await self._google.import_doc(token, doc_id)
        # Carry a source reference back to the originating Doc.
        for block in blocks:
            block.setdefault("data", {}).setdefault("source_doc", doc_id)
        return blocks

    # ---- internals ---------------------------------------------------------

    async def _token_for(
        self, caller: CallerContext, workspace_id: WorkspaceId, scope: str
    ) -> str:
        """Resolve the caller's OWN connection, check the scope, and return a
        fresh access token (refreshing if expired)."""
        await self._access.require_workspace(caller, workspace_id, Role.VIEWER)
        connection = await self._connections.get(
            caller.tenant_id, workspace_id, caller.user_id
        )
        if connection is None or connection.status != STATUS_CONNECTED:
            raise ValidationFailed(
                "no connected Google account — connect Google in settings"
            )
        if not connection.has_scope(scope):
            raise ValidationFailed(
                "this Google permission was not granted — reconnect Google and "
                "enable the required tool group"
            )
        secrets = await self._connections.read_secrets(
            caller.tenant_id, workspace_id, caller.user_id
        )
        assert secrets is not None
        access_encrypted, refresh_encrypted = secrets
        if connection.is_expired(self._clock.now()):
            return await self._refresh(
                caller, workspace_id, connection, refresh_encrypted
            )
        return self._secret_box.decrypt(access_encrypted)

    async def _refresh(
        self,
        caller: CallerContext,
        workspace_id: WorkspaceId,
        connection: GoogleConnection,
        refresh_encrypted: bytes,
    ) -> str:
        now = self._clock.now()
        try:
            tokens = await self._google.refresh(
                self._secret_box.decrypt(refresh_encrypted)
            )
        except Exception as error:
            await self._connections.set_status(
                caller.tenant_id,
                workspace_id,
                caller.user_id,
                STATUS_NEEDS_RECONNECT,
                now,
            )
            raise ValidationFailed(
                "Google session expired — please reconnect Google in settings"
            ) from error
        import dataclasses

        refreshed = dataclasses.replace(
            connection, token_expires_at=tokens.expires_at, updated_at=now
        )
        await self._connections.upsert(
            refreshed,
            access_encrypted=self._secret_box.encrypt(tokens.access_token),
            refresh_encrypted=self._secret_box.encrypt(tokens.refresh_token),
        )
        return tokens.access_token

    def _sign_state(
        self, caller: CallerContext, workspace_id: WorkspaceId
    ) -> str:
        payload = json.dumps(
            {
                "t": str(caller.tenant_id),
                "w": str(workspace_id),
                "u": str(caller.user_id),
                "n": self._ids.new_id(),
            }
        )
        return base64.urlsafe_b64encode(self._secret_box.encrypt(payload)).decode()

    def _verify_state(
        self, state: str
    ) -> tuple[TenantId, WorkspaceId, UserId]:
        try:
            payload = json.loads(
                self._secret_box.decrypt(base64.urlsafe_b64decode(state))
            )
            return (
                TenantId(payload["t"]),
                WorkspaceId(payload["w"]),
                UserId(payload["u"]),
            )
        except Exception as error:
            raise ValidationFailed("invalid OAuth state") from error
