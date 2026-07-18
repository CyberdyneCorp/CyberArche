"""ai-agent spec: turn a meeting recording's transcript into a structured
document. Covers the happy path (structure + create + insert), access
enforcement, and the not-configured / no-token guards."""

from __future__ import annotations

import pytest

from cyberarche.application.ports.llm import LLMResponse
from cyberarche.application.use_cases import UseCases
from cyberarche.application.use_cases.documents import DocumentUseCases
from cyberarche.application.use_cases.meeting_notes import MeetingNotesUseCases
from cyberarche.domain.errors import NotAuthenticated, NotAuthorized, ValidationFailed
from cyberarche.domain.memberships import Role, WorkspaceMembership

STRUCTURED = (
    "## Summary\n\nThe team synced on the roadmap.\n\n"
    "## Key Points\n\n- Shipped the editor\n\n"
    "## Decisions\n\n- Approved Q3 plan\n\n"
    "## Action Items\n\n- Alice: draft the spec\n"
)


async def _workspace(use_cases: UseCases, alice):
    workspace = await use_cases.workspaces.create(alice, name="Docs")
    return workspace


async def test_create_from_recording_structures_and_populates_document(
    use_cases, llm, meetings, alice
):
    workspace = await _workspace(use_cases, alice)
    llm._responses = [LLMResponse(text=STRUCTURED, model="scripted-test-model")]

    document = await use_cases.meeting_notes.create_from_recording(
        alice,
        workspace_id=workspace.id,
        recording_id="rec-1",
        access_token="alice-token",
    )

    # Title comes from the recording headline.
    assert document.title == "Weekly standup"

    # The transcript (source of truth) was handed to the LLM.
    (system, user) = llm.requests[0]
    assert system.role == "system"
    assert "Alice: hello everyone. Bob: hi." in user.content

    # The recording was read with the caller's delegated token.
    assert meetings.tokens == ["alice-token"]

    # The structured content was inserted into the new document as blocks.
    blocks = await use_cases.realtime.read_blocks(alice, document.id)
    texts = " ".join(str(b.get("data", {})) for b in blocks)
    assert "Summary" in texts
    assert "Action Items" in texts
    assert "draft the spec" in texts


async def test_list_recordings_returns_the_providers_recordings(
    use_cases, meetings, alice
):
    recordings = await use_cases.meeting_notes.list_recordings(alice, "alice-token")

    assert [r.id for r in recordings] == ["rec-1"]
    assert meetings.tokens == ["alice-token"]


async def test_viewer_without_edit_access_is_refused_and_no_document_created(
    use_cases, memberships, clock, llm, alice
):
    from tests.conftest import caller

    viewer = caller("carol", "acme")
    workspace = await _workspace(use_cases, alice)
    await memberships.add_workspace_member(
        WorkspaceMembership(
            workspace_id=workspace.id,
            user_id=viewer.user_id,
            role=Role.VIEWER,
            granted_at=clock.now(),
        )
    )
    llm._responses = [LLMResponse(text=STRUCTURED)]

    with pytest.raises(NotAuthorized):
        await use_cases.meeting_notes.create_from_recording(
            viewer,
            workspace_id=workspace.id,
            recording_id="rec-1",
            access_token="carol-token",
        )

    # A viewer sees no documents created in the workspace.
    assert await use_cases.documents.children(viewer, workspace_id=workspace.id) == []


async def test_meetings_not_configured_raises_and_creates_no_document(
    use_cases, llm, alice
):
    workspace = await _workspace(use_cases, alice)
    # A use case with no meetings port configured.
    unconfigured = MeetingNotesUseCases(
        None, llm, use_cases.documents, use_cases.agent, _ids(use_cases)
    )

    with pytest.raises(ValidationFailed):
        await unconfigured.create_from_recording(
            alice,
            workspace_id=workspace.id,
            recording_id="rec-1",
            access_token="alice-token",
        )

    assert await use_cases.documents.children(alice, workspace_id=workspace.id) == []
    # The LLM was never called.
    assert llm.requests == []


async def test_list_recordings_raises_when_not_configured(use_cases, llm, alice):
    unconfigured = MeetingNotesUseCases(
        None, llm, use_cases.documents, use_cases.agent, _ids(use_cases)
    )
    with pytest.raises(ValidationFailed):
        await unconfigured.list_recordings(alice, "alice-token")


async def test_missing_access_token_raises_sign_in_required(use_cases, llm, alice):
    workspace = await _workspace(use_cases, alice)
    with pytest.raises(NotAuthenticated):
        await use_cases.meeting_notes.create_from_recording(
            alice,
            workspace_id=workspace.id,
            recording_id="rec-1",
            access_token="",
        )
    assert await use_cases.documents.children(alice, workspace_id=workspace.id) == []


def _ids(use_cases: UseCases):
    """Reuse the same id generator the wired document use cases use."""
    documents: DocumentUseCases = use_cases.documents
    return documents._ids
