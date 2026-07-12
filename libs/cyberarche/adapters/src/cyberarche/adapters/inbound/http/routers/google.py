"""Google Workspace connector endpoints (google-workspace-connector spec):
per-user OAuth connect/callback/disconnect + status, plus the explicit
create-event action (never an autonomous agent tool)."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from cyberarche.adapters.inbound.http.dependencies import Caller, Cases
from cyberarche.domain.google_workspace import GoogleConnection
from cyberarche.domain.ids import WorkspaceId

router = APIRouter(tags=["google"])


class StatusResponse(BaseModel):
    connected: bool
    configured: bool
    email: str | None = None
    status: str | None = None
    scopes: list[str] = []
    expires_at: datetime | None = None

    @staticmethod
    def of(connection: GoogleConnection | None, *, configured: bool) -> "StatusResponse":
        if connection is None:
            return StatusResponse(connected=False, configured=configured)
        return StatusResponse(
            connected=connection.is_usable(),
            configured=True,
            email=connection.google_email,
            status=connection.status,
            scopes=connection.scopes,
            expires_at=connection.token_expires_at,
        )


class ConnectResponse(BaseModel):
    url: str


class CreateEventRequest(BaseModel):
    summary: str
    start: str
    end: str
    attendees: list[str] = []


def _require_google(cases: Cases):
    if cases.google is None:
        raise HTTPException(status_code=404, detail="Google connector not configured")
    return cases.google


@router.get("/api/v1/workspaces/{workspace_id}/google/status")
async def status(workspace_id: str, cases: Cases, caller: Caller) -> StatusResponse:
    if cases.google is None:
        return StatusResponse(connected=False, configured=False)
    connection = await cases.google.status(caller, WorkspaceId(workspace_id))
    return StatusResponse.of(connection, configured=True)


@router.get("/api/v1/workspaces/{workspace_id}/google/connect")
async def connect(
    workspace_id: str, groups: str, cases: Cases, caller: Caller
) -> ConnectResponse:
    google = _require_google(cases)
    group_list = [g.strip() for g in groups.split(",") if g.strip()]
    url = await google.connect(caller, WorkspaceId(workspace_id), group_list)
    return ConnectResponse(url=url)


@router.get("/api/v1/google/callback")
async def callback(request: Request, cases: Cases) -> HTMLResponse:
    # Google redirects the browser here; authority comes from the signed state,
    # so this route takes no Caller. A bad/missing state is rejected before any
    # token is stored.
    google = _require_google(cases)
    state = request.query_params.get("state", "")
    code = request.query_params.get("code", "")
    if not state or not code:
        raise HTTPException(status_code=400, detail="missing state or code")
    await google.complete_connect(state, code)
    return HTMLResponse(
        "<!doctype html><meta charset=utf-8>"
        "<body style='font-family:sans-serif;padding:40px'>"
        "<h2>Google connected ✓</h2><p>You can close this tab and return to "
        "CyberArche.</p><script>window.close?.()</script></body>"
    )


@router.delete("/api/v1/workspaces/{workspace_id}/google", status_code=204)
async def disconnect(workspace_id: str, cases: Cases, caller: Caller) -> None:
    google = _require_google(cases)
    await google.disconnect(caller, WorkspaceId(workspace_id))


@router.post("/api/v1/workspaces/{workspace_id}/google/calendar/events")
async def create_event(
    workspace_id: str, body: CreateEventRequest, cases: Cases, caller: Caller
) -> dict:
    google = _require_google(cases)
    event_id = await google.calendar_create_event(
        caller,
        WorkspaceId(workspace_id),
        summary=body.summary,
        start=body.start,
        end=body.end,
        attendees=body.attendees,
    )
    return {"event_id": event_id}
