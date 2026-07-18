"""Meeting-notes use cases (ai-agent spec): turn one of the caller's meeting
recordings into a new structured document.

The recording is read with the caller's own delegated access token so the
provider enforces per-user access; the transcript is then structured by the LLM
(a single, tool-free call) and written into a freshly created document as
editable blocks — the agent inserts them as a CRDT peer, so the result is live
and attributed. Creating the document enforces edit access like any other
document create.
"""

from __future__ import annotations

from cyberarche.application.kernel import CallerContext
from cyberarche.application.ports.llm import LLMMessage, LLMPort
from cyberarche.application.ports.meetings import (
    MeetingsPort,
    MeetingSummary,
    MeetingTranscript,
)
from cyberarche.application.ports.telemetry import IdPort
from cyberarche.application.use_cases.agent import AgentUseCases, _answer_blocks
from cyberarche.application.use_cases.documents import DocumentUseCases
from cyberarche.domain.documents import Document
from cyberarche.domain.errors import NotAuthenticated, ValidationFailed
from cyberarche.domain.ids import TeamspaceId, WorkspaceId

_STRUCTURE_SYSTEM = (
    "You turn a meeting transcript into a clean structured document. Output "
    "GitHub-flavored markdown with these sections as `##` headings in order: "
    "Summary, Key Points, Decisions, Action Items. Use bullet lists. Be faithful "
    "to the transcript; if a section has nothing, write '_None._'. Output only "
    "the document, no preamble."
)


class MeetingNotesUseCases:
    def __init__(
        self,
        meetings: MeetingsPort | None,
        llm: LLMPort,
        documents: DocumentUseCases,
        agent: AgentUseCases,
        ids: IdPort,
    ) -> None:
        self._meetings = meetings
        self._llm = llm
        self._documents = documents
        self._agent = agent
        self._ids = ids

    async def list_recordings(
        self,
        caller: CallerContext,
        access_token: str,
        *,
        limit: int = 20,
    ) -> list[MeetingSummary]:
        """The caller's recent recordings, read with their delegated token."""
        meetings = self._require_meetings(access_token)
        return await meetings.list_recordings(access_token, limit=limit)

    async def create_from_recording(
        self,
        caller: CallerContext,
        *,
        workspace_id: WorkspaceId,
        recording_id: str,
        access_token: str,
        teamspace_id: TeamspaceId | None = None,
    ) -> Document:
        """Fetch a recording's transcript, structure it with the LLM, and create
        a document populated with the structured content as editable blocks."""
        meetings = self._require_meetings(access_token)
        rec = await meetings.get_recording(access_token, recording_id)
        response = await self._llm.complete(_structure_prompt(rec))
        title = (rec.headline or "Meeting notes").strip()[:200] or "Meeting notes"
        doc = await self._documents.create(
            caller, workspace_id=workspace_id, title=title, teamspace_id=teamspace_id
        )
        blocks = _answer_blocks(self._ids, response.text)
        if blocks:
            await self._agent.apply_blocks(caller, doc.id, blocks)
        return doc

    def _require_meetings(self, access_token: str) -> MeetingsPort:
        """Guard both entry points: meetings must be configured and the caller
        must present a delegable access token."""
        if self._meetings is None:
            raise ValidationFailed("meeting transcripts are not configured")
        if not access_token:
            raise NotAuthenticated("sign in required to access meetings")
        return self._meetings


def _structure_prompt(rec: MeetingTranscript) -> list[LLMMessage]:
    """The tool-free structuring prompt: the transcript is the source of truth,
    with the provider's own summary fields as supporting hints when present."""
    parts: list[str] = []
    if rec.abstract:
        parts.append(f"Provider summary (hint): {rec.abstract}")
    if rec.bullets:
        parts.append("Provider key points (hint):\n" + _bullets(rec.bullets))
    if rec.action_items:
        parts.append("Provider action items (hint):\n" + _bullets(rec.action_items))
    transcript = rec.transcript or "(no transcript available)"
    parts.append(f"Transcript (source of truth):\n{transcript}")
    return [
        LLMMessage(role="system", content=_STRUCTURE_SYSTEM),
        LLMMessage(role="user", content="\n\n".join(parts)),
    ]


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)
