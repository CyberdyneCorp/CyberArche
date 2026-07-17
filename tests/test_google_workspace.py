"""Google Workspace connector: OAuth lifecycle, scope-gating, auto-refresh,
per-user isolation, doc mapping, agent tools (google-workspace-connector spec)."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

import pytest

from cyberarche.application.ports.llm import LLMResponse, ToolCall
from cyberarche.domain.errors import ValidationFailed
from cyberarche.domain.google_workspace import (
    SCOPE_GROUPS,
    STATUS_NEEDS_RECONNECT,
    map_doc_elements,
    scopes_for_groups,
)
from cyberarche.domain.memberships import Role, WorkspaceMembership

from tests.conftest import caller
from tests.test_agent import make_document


# ---- domain ----------------------------------------------------------------


def test_scopes_for_groups_is_minimal():
    only_cal = scopes_for_groups(["calendar"])
    assert only_cal == SCOPE_GROUPS["calendar"]
    assert not any("gmail" in s or "drive" in s for s in only_cal)


def test_map_doc_elements():
    blocks = map_doc_elements(
        [
            {"type": "heading", "text": "Title", "level": 1},
            {"type": "paragraph", "text": "Body"},
            {"type": "bulleted_list", "text": "point"},
            {"type": "code", "text": "print(1)"},
        ]
    )
    assert [b["type"] for b in blocks] == [
        "heading",
        "paragraph",
        "bulleted_list",
        "code",
    ]
    assert blocks[0]["data"]["level"] == 1


# ---- OAuth lifecycle -------------------------------------------------------


async def _connect(use_cases, google_port, caller_ctx, workspace_id, groups):
    """Drive the connect + callback flow with the fake port."""
    google_port.granted_scopes = scopes_for_groups(groups)
    url = await use_cases.google.connect(caller_ctx, workspace_id, groups)
    # The consent URL requests exactly the chosen scopes.
    for scope in scopes_for_groups(groups):
        assert scope in url
    state = url.split("state=")[1].split("&")[0]
    return await use_cases.google.complete_connect(state, "auth-code")


async def test_complete_oauth_stores_connection(use_cases, google_port, alice):
    workspace, _ = await make_document(use_cases, alice)
    conn = await _connect(
        use_cases, google_port, alice, workspace.id, ["gmail_read", "calendar"]
    )
    assert conn.status == "connected"
    status = await use_cases.google.status(alice, workspace.id)
    assert status is not None and status.google_email == "user@example.com"


async def test_consent_requests_only_chosen_group(use_cases, alice):
    workspace, _ = await make_document(use_cases, alice)
    url = await use_cases.google.connect(alice, workspace.id, ["calendar"])
    assert "calendar" in url
    assert "gmail" not in url and "drive" not in url


async def test_callback_rejects_bad_state(use_cases, google_port, alice):
    with pytest.raises(ValidationFailed):
        await use_cases.google.complete_connect("not-a-valid-state", "code")


async def test_tokens_are_never_returned_in_plaintext(
    use_cases, google_port, google_repo, alice
):
    workspace, _ = await make_document(use_cases, alice)
    await _connect(use_cases, google_port, alice, workspace.id, ["gmail_read"])
    conn = await use_cases.google.status(alice, workspace.id)
    # The metadata object has no token fields at all.
    assert not any("token" in f for f in conn.__slots__ if "expires" not in f)
    # Stored secrets are ciphertext, not the plaintext access token.
    secrets = await google_repo.read_secrets(alice.tenant_id, workspace.id, alice.user_id)
    assert secrets is not None
    assert b"access-auth-code" not in secrets[0]


# ---- refresh ---------------------------------------------------------------


async def test_expired_token_is_refreshed(use_cases, google_port, google_repo, alice):
    workspace, _ = await make_document(use_cases, alice)
    await _connect(use_cases, google_port, alice, workspace.id, ["gmail_read"])
    # Force the stored token to be expired.
    key = google_repo._key(alice.tenant_id, workspace.id, alice.user_id)
    stored, acc, ref = google_repo._items[key]
    google_repo._items[key] = (
        dataclasses.replace(stored, token_expires_at=datetime(2020, 1, 1, tzinfo=UTC)),
        acc,
        ref,
    )
    # A tool call triggers a refresh and returns a fresh access token.
    await use_cases.google.gmail_search(alice, workspace.id, "hi")
    assert "access-refreshed" in google_port.tokens_used


async def test_refresh_failure_sets_needs_reconnect(
    use_cases, google_port, google_repo, alice
):
    workspace, _ = await make_document(use_cases, alice)
    await _connect(use_cases, google_port, alice, workspace.id, ["gmail_read"])
    key = google_repo._key(alice.tenant_id, workspace.id, alice.user_id)
    stored, acc, ref = google_repo._items[key]
    google_repo._items[key] = (
        dataclasses.replace(stored, token_expires_at=datetime(2020, 1, 1, tzinfo=UTC)),
        acc,
        ref,
    )
    google_port.refresh_fails = True
    with pytest.raises(ValidationFailed):
        await use_cases.google.gmail_search(alice, workspace.id, "hi")
    status = await use_cases.google.status(alice, workspace.id)
    assert status.status == STATUS_NEEDS_RECONNECT


# ---- scope gating + isolation ----------------------------------------------


async def test_missing_scope_blocks_tool_without_calling_google(
    use_cases, google_port, alice
):
    workspace, _ = await make_document(use_cases, alice)
    # Connected with only Calendar → a Gmail tool must be blocked.
    await _connect(use_cases, google_port, alice, workspace.id, ["calendar"])
    with pytest.raises(ValidationFailed):
        await use_cases.google.gmail_search(alice, workspace.id, "hi")
    assert google_port.tokens_used == []  # Google was never called


def test_gmail_is_read_only_no_write_scope_or_tool():
    """Gmail must be read-only: no compose/send/modify scope, and the use case
    exposes no write method."""
    assert SCOPE_GROUPS["gmail_read"] == [
        "https://www.googleapis.com/auth/gmail.readonly"
    ]
    assert not any(
        w in s
        for scopes in SCOPE_GROUPS.values()
        for s in scopes
        for w in ("gmail.compose", "gmail.send", "gmail.modify")
    )
    from cyberarche.application.use_cases.google_workspace import GoogleWorkspaceUseCases

    assert not hasattr(GoogleWorkspaceUseCases, "gmail_draft")


def test_calendar_is_the_only_writable_surface():
    """Calendar uses the narrow events/freebusy scopes (not full calendar), and
    it is the only place a write scope appears; everything else is *.readonly."""
    assert set(SCOPE_GROUPS["calendar"]) == {
        "https://www.googleapis.com/auth/calendar.events",
        "https://www.googleapis.com/auth/calendar.freebusy",
    }
    assert "https://www.googleapis.com/auth/calendar" not in SCOPE_GROUPS["calendar"]
    writable = [
        s
        for scopes in SCOPE_GROUPS.values()
        for s in scopes
        if not s.endswith(".readonly") and not s.endswith(".freebusy")
    ]
    assert writable == ["https://www.googleapis.com/auth/calendar.events"]


async def test_agent_can_create_a_calendar_event(use_cases, google_port, alice):
    workspace, _ = await make_document(use_cases, alice)
    await _connect(use_cases, google_port, alice, workspace.id, ["calendar"])
    event_id = await use_cases.google.calendar_create_event(
        alice, workspace.id, summary="Sync", start="2026-07-20T09:00:00Z",
        end="2026-07-20T09:30:00Z", attendees=["x@y.com"],
    )
    assert event_id == "event-1"
    assert len(google_port.created_events) == 1


async def test_sheets_and_slides_are_read_only(use_cases, google_port, alice):
    workspace, _ = await make_document(use_cases, alice)
    await _connect(use_cases, google_port, alice, workspace.id, ["sheets", "slides"])
    assert "sheet-1" in await use_cases.google.sheets_read(alice, workspace.id, "sheet-1")
    assert "deck-1" in await use_cases.google.slides_read(alice, workspace.id, "deck-1")


async def test_sheets_blocked_without_scope(use_cases, google_port, alice):
    workspace, _ = await make_document(use_cases, alice)
    await _connect(use_cases, google_port, alice, workspace.id, ["gmail_read"])
    with pytest.raises(ValidationFailed):
        await use_cases.google.sheets_read(alice, workspace.id, "sheet-1")
    assert google_port.tokens_used == []


async def test_user_b_cannot_use_user_a_connection(
    use_cases, google_port, memberships, clock, alice
):
    workspace, _ = await make_document(use_cases, alice)
    await _connect(use_cases, google_port, alice, workspace.id, ["gmail_read"])
    bob = caller("bob", "acme")
    await memberships.add_workspace_member(
        WorkspaceMembership(
            workspace_id=workspace.id, user_id=bob.user_id,
            role=Role.EDITOR, granted_at=clock.now(),
        )
    )
    # Bob has no connection → treated as not connected, never uses Alice's.
    assert await use_cases.google.status(bob, workspace.id) is None
    with pytest.raises(ValidationFailed):
        await use_cases.google.gmail_search(bob, workspace.id, "hi")


async def test_disconnect_revokes_and_removes(use_cases, google_port, alice):
    workspace, _ = await make_document(use_cases, alice)
    await _connect(use_cases, google_port, alice, workspace.id, ["gmail_read"])
    await use_cases.google.disconnect(alice, workspace.id)
    assert google_port.revoked  # revoked at Google
    assert await use_cases.google.status(alice, workspace.id) is None
    with pytest.raises(ValidationFailed):
        await use_cases.google.gmail_search(alice, workspace.id, "hi")


# ---- agent tools -----------------------------------------------------------


async def test_google_tools_appear_only_when_connected(
    use_cases, google_port, alice
):
    workspace, document = await make_document(use_cases, alice)
    before = await use_cases.agent._available_tools(
        alice, workspace.id, document.id, None, "tok"
    )
    assert not any(t.name.startswith("google_") for t in before)

    await _connect(use_cases, google_port, alice, workspace.id, ["gmail_read"])
    after = await use_cases.agent._available_tools(
        alice, workspace.id, document.id, None, "tok"
    )
    names = {t.name for t in after}
    assert "google_gmail_search" in names
    # No compose/calendar tools — that scope wasn't granted.
    assert "google_gmail_draft" not in names and "google_calendar_list" not in names


async def test_agent_imports_a_google_doc_as_blocks(
    use_cases, llm, google_port, alice
):
    workspace, document = await make_document(use_cases, alice)
    await _connect(use_cases, google_port, alice, workspace.id, ["drive"])
    llm._responses = [
        LLMResponse(
            text="",
            tool_calls=(
                ToolCall(id="c1", name="google_import_doc", arguments={"doc_id": "D1"}),
            ),
        ),
        LLMResponse(text="Imported.", model="m"),
    ]
    await use_cases.agent.ask(
        alice, document.id, instruction="import doc D1", access_token="tok"
    )
    state = await use_cases.realtime.current_state(alice, document.id)
    texts = [
        b["data"].get("text", "")
        for b in use_cases.agent._engine.read_blocks(state)
    ]
    assert any("Imported" in t for t in texts)


# ---- HTTP router -----------------------------------------------------------


def _auth(token: str = "alice-token") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_google_router_reports_unconfigured(api):
    # The default test app has no Google credentials → connector not configured.
    ws = api.post("/api/v1/workspaces", json={"name": "WS"}, headers=_auth()).json()["id"]
    status = api.get(f"/api/v1/workspaces/{ws}/google/status", headers=_auth()).json()
    assert status["configured"] is False and status["connected"] is False
    # Connect is a 404 when unconfigured.
    connect = api.get(
        f"/api/v1/workspaces/{ws}/google/connect?groups=calendar", headers=_auth()
    )
    assert connect.status_code == 404
