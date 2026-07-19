"""document-import spec: import a file/Notion export into private documents.

Covers a single Markdown file (private, titled from the first heading, blocks
applied), access enforcement, a Notion `.zip` (per-file docs, folder nesting,
stripped titles), and `import_upload` dispatch by extension.
"""

from __future__ import annotations

import io
import zipfile

import pytest
from openpyxl import Workbook
from pypdf import PdfWriter

from cyberarche.application.use_cases import UseCases
from cyberarche.domain.collections import PropertyType
from cyberarche.domain.errors import NotAuthorized
from cyberarche.domain.ids import CollectionId
from cyberarche.domain.memberships import Role, WorkspaceMembership

MARKDOWN = "# Project Plan\n\nIntro paragraph.\n\n- milestone one\n- milestone two"

SPREADSHEET_CSV = (
    "Name,Age,City,Rank\n"
    "Alice,30,NYC,1\n"
    "Bob,25,LA,top\n"
).encode()


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


def _xlsx(rows: list[list[object]]) -> bytes:
    workbook = Workbook()
    for row in rows:
        workbook.active.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _pdf(text: str) -> bytes:
    """A minimal blank one-page PDF (pypdf can't render text, but the page is
    enough for `extract_blocks` to produce a document)."""
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


async def _collection_of_embedded_doc(use_cases, alice, doc):
    """Read the single `collection_view` block of `doc` and load its collection
    plus its rows via the default view."""
    blocks = await use_cases.realtime.read_blocks(alice, doc.id)
    assert len(blocks) == 1
    block = blocks[0]
    assert block["type"] == "collection_view"
    collection_id = CollectionId(block["data"]["collection_id"])
    view_id = block["data"]["view_id"]
    collection = await use_cases.collections.get_collection(alice, collection_id)
    rows = await use_cases.collections.query_view(alice, collection_id, view_id)
    return collection, view_id, rows


async def test_import_spreadsheet_builds_collection_with_typed_properties(
    use_cases, alice
):
    workspace = await _workspace(use_cases, alice)

    doc = await use_cases.document_import.import_spreadsheet(
        alice, workspace_id=workspace.id, filename="people.csv", content=SPREADSHEET_CSV
    )

    # The embedding document is private and named from the file stem.
    assert doc.title == "people"
    assert doc.teamspace_id is None and doc.parent_id is None

    collection, view_id, rows = await _collection_of_embedded_doc(use_cases, alice, doc)
    assert collection.name == "people"
    # The default view is what the block embeds.
    assert view_id == collection.views[0].id

    # Properties come from header[1:] (the first column is the title). A column
    # that is all-numeric infers NUMBER; a mixed column stays TEXT.
    by_name = {p.name: p for p in collection.properties}
    assert set(by_name) == {"Age", "City", "Rank"}
    assert by_name["Age"].type == PropertyType.NUMBER
    assert by_name["City"].type == PropertyType.TEXT
    assert by_name["Rank"].type == PropertyType.TEXT  # mixed "1"/"top" -> TEXT

    # One row per data line; the first column is the title, the rest are values.
    by_title = {row.title: row for row in rows}
    assert set(by_title) == {"Alice", "Bob"}
    alice_row = by_title["Alice"]
    assert alice_row.properties[by_name["Age"].id] == 30  # numeric string coerced
    assert alice_row.properties[by_name["City"].id] == "NYC"
    assert by_title["Bob"].properties[by_name["Age"].id] == 25


async def test_import_spreadsheet_xlsx_first_column_is_title(use_cases, alice):
    workspace = await _workspace(use_cases, alice)
    content = _xlsx([["Item", "Qty"], ["Widget", 3]])

    doc = await use_cases.document_import.import_spreadsheet(
        alice, workspace_id=workspace.id, filename="stock.xlsx", content=content
    )

    collection, _view, rows = await _collection_of_embedded_doc(use_cases, alice, doc)
    (qty,) = collection.properties
    assert qty.name == "Qty" and qty.type == PropertyType.NUMBER
    assert [r.title for r in rows] == ["Widget"]
    assert rows[0].properties[qty.id] == 3


async def test_import_spreadsheet_empty_sheet_creates_empty_collection(use_cases, alice):
    workspace = await _workspace(use_cases, alice)

    doc = await use_cases.document_import.import_spreadsheet(
        alice, workspace_id=workspace.id, filename="blank.csv", content=b""
    )

    collection, _view, rows = await _collection_of_embedded_doc(use_cases, alice, doc)
    assert collection.name == "blank"
    assert collection.properties == ()
    assert rows == []


async def test_import_spreadsheet_single_column_yields_titles_only(use_cases, alice):
    workspace = await _workspace(use_cases, alice)
    content = b"Fruit\nApple\nPear\n"

    doc = await use_cases.document_import.import_spreadsheet(
        alice, workspace_id=workspace.id, filename="fruit.csv", content=content
    )

    collection, _view, rows = await _collection_of_embedded_doc(use_cases, alice, doc)
    assert collection.properties == ()
    assert sorted(r.title for r in rows) == ["Apple", "Pear"]


async def test_import_spreadsheet_requires_edit_access(
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
        await use_cases.document_import.import_spreadsheet(
            viewer,
            workspace_id=workspace.id,
            filename="people.csv",
            content=SPREADSHEET_CSV,
        )

    assert await use_cases.collections.list_collections(alice, workspace.id) == []


async def test_import_file_pdf_creates_a_document(use_cases, alice):
    workspace = await _workspace(use_cases, alice)

    doc = await use_cases.document_import.import_file(
        alice, workspace_id=workspace.id, filename="report.pdf", content=_pdf("hi")
    )

    # A blank PDF has no extractable text, so the title falls back to the stem.
    assert doc.title == "report"
    assert doc.teamspace_id is None


async def test_import_upload_dispatches_spreadsheet_pdf_and_file(use_cases, alice):
    workspace = await _workspace(use_cases, alice)

    sheet = await use_cases.document_import.import_upload(
        alice, workspace_id=workspace.id, filename="people.csv", content=SPREADSHEET_CSV
    )
    assert len(sheet) == 1
    blocks = await use_cases.realtime.read_blocks(alice, sheet[0].id)
    assert [b["type"] for b in blocks] == ["collection_view"]

    xlsx = await use_cases.document_import.import_upload(
        alice,
        workspace_id=workspace.id,
        filename="stock.xlsx",
        content=_xlsx([["Item", "Qty"], ["Widget", 3]]),
    )
    xlsx_blocks = await use_cases.realtime.read_blocks(alice, xlsx[0].id)
    assert [b["type"] for b in xlsx_blocks] == ["collection_view"]

    pdf = await use_cases.document_import.import_upload(
        alice, workspace_id=workspace.id, filename="report.pdf", content=_pdf("x")
    )
    assert len(pdf) == 1 and pdf[0].title == "report"

    markdown = await use_cases.document_import.import_upload(
        alice, workspace_id=workspace.id, filename="plan.md", content=MARKDOWN.encode()
    )
    assert markdown[0].title == "Project Plan"


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
