"""Meeting-notes endpoints (ai-agent spec): list the caller's recordings and
turn one into a new structured document. Recordings are read with the caller's
delegated access token so the provider enforces per-user access."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from cyberarche.adapters.inbound.http.dependencies import (
    AccessToken,
    Caller,
    Cases,
)
from cyberarche.adapters.inbound.http.schemas import DocumentResponse
from cyberarche.application.ports.meetings import MeetingSummary
from cyberarche.domain.ids import TeamspaceId, WorkspaceId

router = APIRouter(prefix="/api/v1", tags=["meetings"])


class RecordingResponse(BaseModel):
    id: str
    status: str
    captured_at: str | None = None
    headline: str | None = None

    @staticmethod
    def from_domain(recording: MeetingSummary) -> "RecordingResponse":
        return RecordingResponse(
            id=recording.id,
            status=recording.status,
            captured_at=recording.captured_at,
            headline=recording.headline,
        )


class MeetingNotesRequest(BaseModel):
    recording_id: str
    teamspace_id: str | None = None


@router.get("/meetings")
async def list_meetings(
    cases: Cases, caller: Caller, access_token: AccessToken
) -> list[RecordingResponse]:
    """The caller's recent meeting recordings, so they can pick one."""
    recordings = await cases.meeting_notes.list_recordings(caller, access_token)
    return [RecordingResponse.from_domain(r) for r in recordings]


@router.post("/workspaces/{workspace_id}/meeting-notes", status_code=201)
async def create_meeting_notes(
    workspace_id: str,
    body: MeetingNotesRequest,
    cases: Cases,
    caller: Caller,
    access_token: AccessToken,
) -> DocumentResponse:
    """Structure a recording's transcript into a new document and return it."""
    document = await cases.meeting_notes.create_from_recording(
        caller,
        workspace_id=WorkspaceId(workspace_id),
        recording_id=body.recording_id,
        access_token=access_token,
        teamspace_id=TeamspaceId(body.teamspace_id) if body.teamspace_id else None,
    )
    return DocumentResponse.from_domain(document)
