"""document-import spec: import a file/Notion export into private documents.

Covers a single Markdown file (private, titled from the first heading, blocks
applied), access enforcement, a Notion `.zip` (per-file docs, folder nesting,
stripped titles), and `import_upload` dispatch by extension.
"""

from __future__ import annotations

import io
import zipfile

import pytest

from cyberarche.application.use_cases import UseCases
from cyberarche.domain.errors import NotAuthorized
from cyberarche.domain.memberships import Role, WorkspaceMembership

MARKDOWN = "# Project Plan\n\nIntro paragraph.\n\n- milestone one\n- milestone two"


async def _workspace(use_cases: UseCases, alice):
    return await use_cases.workspaces.create(alice, name="Docs")


async def test_import_file_creates_private_document_titled_from_first_heading(
    use_cases, alice
):
    workspace = await _workspace(use_cases, alice)

    doc = await use_cases.document_import.import_file(
        alice,
        workspace_id=workspace.id,
        filename="plan.md",
        content=MARKDOWN.encode(),
    )

    assert doc.title == "Project Plan"
    # Private: no teamspace, a root document.
    assert doc.teamspace_id is None
    assert doc.parent_id is None

    blocks = await use_cases.realtime.read_blocks(alice, doc.id)
    types = [b["type"] for b in blocks]
    assert types == ["heading", "paragraph", "bulleted_list", "bulleted_list"]


async def test_import_file_falls_back_to_filename_stem_when_no_heading(
    use_cases, alice
):
    workspace = await _workspace(use_cases, alice)

    doc = await use_cases.document_import.import_file(
        alice,
        workspace_id=workspace.id,
        filename="meeting-notes.md",
        content=b"Just some prose, no heading.",
    )

    assert doc.title == "meeting-notes"


async def test_viewer_without_edit_access_is_refused_and_no_document_created(
    use_cases, memberships, clock, alice
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

    with pytest.raises(NotAuthorized):
        await use_cases.document_import.import_file(
            viewer,
            workspace_id=workspace.id,
            filename="plan.md",
            content=MARKDOWN.encode(),
        )

    assert await use_cases.documents.children(viewer, workspace_id=workspace.id) == []


def _notion_zip(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, text in files.items():
            archive.writestr(name, text)
    return buffer.getvalue()


async def test_import_notion_zip_nests_documents_and_strips_ids(use_cases, alice):
    workspace = await _workspace(use_cases, alice)
    hexid = "0123456789abcdef0123456789abcdef"
    content = _notion_zip(
        {
            f"Area {hexid}/Team {hexid}/Page {hexid}.md": "# Page\n\nBody.",
            f"Area {hexid}/Top {hexid}.md": "# Top\n\nText.",
            "README.txt": "ignored, not markdown",
        }
    )

    docs = await use_cases.document_import.import_notion_zip(
        alice, workspace_id=workspace.id, content=content
    )

    by_title = {d.title: d for d in docs}
    # Folder parents created, titles stripped of the Notion id and .md.
    assert "Area" in by_title
    assert "Team" in by_title
    assert "Page" in by_title
    assert "Top" in by_title

    # Nesting: Area (root) -> Team -> Page; Area -> Top.
    assert by_title["Area"].parent_id is None
    assert by_title["Team"].parent_id == by_title["Area"].id
    assert by_title["Page"].parent_id == by_title["Team"].id
    assert by_title["Top"].parent_id == by_title["Area"].id

    # Roots come first in the returned list.
    assert docs[0].title == "Area"

    # The page's markdown was applied as blocks.
    blocks = await use_cases.realtime.read_blocks(alice, by_title["Page"].id)
    assert [b["type"] for b in blocks] == ["heading", "paragraph"]


async def test_import_upload_dispatches_zip_vs_single_file(use_cases, alice):
    workspace = await _workspace(use_cases, alice)

    single = await use_cases.document_import.import_upload(
        alice,
        workspace_id=workspace.id,
        filename="plan.md",
        content=MARKDOWN.encode(),
    )
    assert len(single) == 1
    assert single[0].title == "Project Plan"

    zipped = await use_cases.document_import.import_upload(
        alice,
        workspace_id=workspace.id,
        filename="export.zip",
        content=_notion_zip({"Note.md": "# Note\n\nHi."}),
    )
    assert [d.title for d in zipped] == ["Note"]


def _auth(token: str = "alice-token") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_import_endpoint_returns_created_documents(api):
    ws = api.post("/api/v1/workspaces", json={"name": "WS"}, headers=_auth()).json()

    resp = api.post(
        f"/api/v1/workspaces/{ws['id']}/import",
        files={"file": ("plan.md", MARKDOWN.encode(), "text/markdown")},
        headers=_auth(),
    )

    assert resp.status_code == 201
    body = resp.json()
    assert isinstance(body, list) and len(body) == 1
    assert body[0]["title"] == "Project Plan"
    assert body[0]["parent_id"] is None
