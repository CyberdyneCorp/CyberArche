"""document-search spec: full-text search over titles and block content."""

from __future__ import annotations

import pytest

from cyberarche.domain.errors import NotAuthorized
from cyberarche.domain.memberships import Role, WorkspaceMembership

from tests.conftest import caller
from tests.test_agent import make_document, seed_blocks


async def test_title_match_is_flagged_as_a_title_hit(use_cases, alice):
    workspace, document = await make_document(use_cases, alice, title="Roadmap 2026")

    hits = await use_cases.search.search(alice, workspace.id, query="roadmap")

    assert [(h.document.id, h.field) for h in hits] == [(document.id, "title")]
    assert hits[0].snippet == ""


async def test_content_match_returns_a_snippet_with_the_term(use_cases, alice):
    workspace, document = await make_document(use_cases, alice, title="Untitled")
    await seed_blocks(
        use_cases,
        alice,
        document.id,
        ["The quarterly launch is scheduled for the third of March next year."],
    )

    hits = await use_cases.search.search(alice, workspace.id, query="launch")

    assert len(hits) == 1
    assert hits[0].document.id == document.id
    assert hits[0].field == "content"
    assert "launch" in hits[0].snippet.lower()


async def test_documents_the_caller_cannot_view_are_excluded(
    use_cases, memberships, clock, alice
):
    # A private (teamspace-less) document is visible only to its creator, even to
    # other workspace members — so it must not leak through search.
    workspace = await use_cases.workspaces.create(alice, name="WS")
    document = await use_cases.documents.create(
        alice, workspace_id=workspace.id, title="Secret plan"
    )
    mallory = caller("mallory", "acme")
    await memberships.add_workspace_member(
        WorkspaceMembership(
            workspace_id=workspace.id,
            user_id=mallory.user_id,
            role=Role.EDITOR,
            granted_at=clock.now(),
        )
    )

    mine = await use_cases.search.search(alice, workspace.id, query="secret")
    theirs = await use_cases.search.search(mallory, workspace.id, query="secret")

    assert [h.document.id for h in mine] == [document.id]
    assert theirs == []


async def test_matches_code_source_and_table_cells(use_cases, alice):
    workspace, document = await make_document(use_cases, alice, title="Untitled")
    await use_cases.agent.apply_blocks(
        alice,
        document.id,
        [
            {"id": "c1", "type": "code", "data": {"source": "print('widget')"}},
            {
                "id": "t1",
                "type": "table",
                "data": {"header": ["Metric"], "rows": [["gadget count"]]},
            },
        ],
    )

    code_hits = await use_cases.search.search(alice, workspace.id, query="widget")
    table_hits = await use_cases.search.search(alice, workspace.id, query="gadget")

    assert [h.field for h in code_hits] == ["content"]
    assert [h.field for h in table_hits] == ["content"]


async def test_non_matching_documents_are_omitted(use_cases, alice):
    workspace, match = await make_document(use_cases, alice, title="Roadmap")
    other = await use_cases.documents.create(
        alice, workspace_id=match.workspace_id, title="Unrelated"
    )
    await seed_blocks(use_cases, alice, other.id, ["nothing to see here"])

    hits = await use_cases.search.search(alice, workspace.id, query="roadmap")

    assert [h.document.id for h in hits] == [match.id]


async def test_limit_caps_the_number_of_hits(use_cases, alice):
    workspace, _ = await make_document(use_cases, alice, title="Report alpha")
    await use_cases.documents.create(
        alice, workspace_id=workspace.id, title="Report beta"
    )

    hits = await use_cases.search.search(alice, workspace.id, query="report", limit=1)

    assert len(hits) == 1


async def test_snippet_is_ellipsised_when_truncated(use_cases, alice):
    workspace, document = await make_document(use_cases, alice, title="Untitled")
    filler = "x " * 200
    await seed_blocks(use_cases, alice, document.id, [f"{filler}needle{filler}"])

    hits = await use_cases.search.search(alice, workspace.id, query="needle")

    assert hits[0].snippet.startswith("…")
    assert hits[0].snippet.endswith("…")
    assert "needle" in hits[0].snippet


async def test_empty_query_returns_nothing(use_cases, alice):
    workspace, _ = await make_document(use_cases, alice, title="Anything")

    assert await use_cases.search.search(alice, workspace.id, query="") == []
    assert await use_cases.search.search(alice, workspace.id, query="   ") == []


async def test_search_requires_workspace_membership(use_cases, alice, bob_other_tenant):
    workspace, _ = await make_document(use_cases, alice, title="Roadmap")

    with pytest.raises(NotAuthorized):
        await use_cases.search.search(bob_other_tenant, workspace.id, query="roadmap")
