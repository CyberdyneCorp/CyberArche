"""Document-import use cases (document-import spec): turn an uploaded file into
one or more documents whose content is real, editable blocks.

A single file (Markdown / .docx / plain text / PDF / CSV / Excel) becomes one
private document; a Notion `.zip` export becomes a tree of documents that mirrors
the export's folder structure. Extraction is delegated to the FileExtractor port;
each document is created with the caller's edit access (it rides `documents.create`)
and populated by the agent as a CRDT peer, so results are live and attributed.
The created documents are private — no teamspace.
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import PurePosixPath

from cyberarche.application.kernel import CallerContext
from cyberarche.application.ports.extraction import FileExtractorPort
from cyberarche.application.ports.telemetry import IdPort
from cyberarche.application.use_cases.agent import AgentUseCases
from cyberarche.application.use_cases.collections import CollectionUseCases
from cyberarche.application.use_cases.documents import DocumentUseCases
from cyberarche.domain.collections import PropertyType
from cyberarche.domain.documents import Document
from cyberarche.domain.ids import CollectionId, DocumentId, WorkspaceId

# Zip-bomb guards: a Notion export is a modest set of markdown files.
_MAX_ENTRIES = 2000
_MAX_FILE_SIZE = 5 * 1024 * 1024

_TITLE_LIMIT = 200
# Notion appends a space + 32-hex page id to every file and folder name.
_NOTION_ID_RE = re.compile(r"\s+[0-9a-fA-F]{32}$")

# A spreadsheet import materializes at most this many data rows; the rest are
# ignored so a huge sheet cannot blow up into an unbounded number of documents.
_MAX_ROWS = 1000

# Spreadsheet extensions that import as a collection (not as document blocks).
_SPREADSHEET_SUFFIXES = (".csv", ".xlsx", ".xlsm")


class ImportUseCases:
    def __init__(
        self,
        documents: DocumentUseCases,
        agent: AgentUseCases,
        extractor: FileExtractorPort,
        collections: CollectionUseCases,
        ids: IdPort,
    ) -> None:
        self._documents = documents
        self._agent = agent
        self._extractor = extractor
        self._collections = collections
        self._ids = ids

    async def import_upload(
        self,
        caller: CallerContext,
        *,
        workspace_id: WorkspaceId,
        filename: str,
        content: bytes,
    ) -> list[Document]:
        """Dispatch by extension: `.zip` -> Notion export, a spreadsheet
        (`.csv`/`.xlsx`) -> a collection embedded in a document, else a single
        document from the file's blocks."""
        suffix = PurePosixPath(filename.lower()).suffix
        if suffix == ".zip":
            return await self.import_notion_zip(
                caller, workspace_id=workspace_id, content=content
            )
        if suffix in _SPREADSHEET_SUFFIXES:
            doc = await self.import_spreadsheet(
                caller, workspace_id=workspace_id, filename=filename, content=content
            )
            return [doc]
        doc = await self.import_file(
            caller, workspace_id=workspace_id, filename=filename, content=content
        )
        return [doc]

    async def import_spreadsheet(
        self,
        caller: CallerContext,
        *,
        workspace_id: WorkspaceId,
        filename: str,
        content: bytes,
    ) -> Document:
        """Import a CSV/Excel sheet as a new collection, then create a private
        document that embeds a view of it. The first column becomes each row's
        title; the remaining columns become typed properties (a column that is
        all-numeric in the data becomes a NUMBER property, else TEXT)."""
        header, rows = self._extractor.extract_table(
            filename=filename, content=content
        )
        name = _filename_stem(filename)
        collection = await self._collections.create_collection(
            caller, workspace_id=workspace_id, name=name
        )
        mapping = await self._build_schema(caller, collection.id, header, rows)
        await self._import_rows(caller, collection.id, rows, mapping)
        return await self._embed_collection(
            caller, workspace_id, name, collection.id, collection.views[0].id
        )

    async def _build_schema(
        self,
        caller: CallerContext,
        collection_id: CollectionId,
        header: list[str],
        rows: list[list[str]],
    ) -> list[tuple[int, str]]:
        """Add one property per column after the first; return the ordered
        ``(column_index, property_id)`` pairs used to fill each row."""
        mapping: list[tuple[int, str]] = []
        for index in range(1, len(header)):
            col_type = _infer_column_type(rows, index)
            updated = await self._collections.add_property(
                caller, collection_id, name=header[index] or "Column", type=col_type
            )
            mapping.append((index, updated.properties[-1].id))
        return mapping

    async def _import_rows(
        self,
        caller: CallerContext,
        collection_id: CollectionId,
        rows: list[list[str]],
        mapping: list[tuple[int, str]],
    ) -> None:
        """Create a capped row per data line: the first column is the title and
        each mapped column's non-empty cell is written as that property's value."""
        for row in rows[:_MAX_ROWS]:
            created = await self._collections.add_row(
                caller, collection_id, title=_cell(row, 0)
            )
            values = {
                property_id: _cell(row, index)
                for index, property_id in mapping
                if _cell(row, index)
            }
            if values:
                await self._collections.set_row_values(caller, created.id, values)

    async def _embed_collection(
        self,
        caller: CallerContext,
        workspace_id: WorkspaceId,
        title: str,
        collection_id: CollectionId,
        view_id: str,
    ) -> Document:
        doc = await self._documents.create(
            caller, workspace_id=workspace_id, title=title
        )
        block = {
            "id": self._ids.new_id(),
            "type": "collection_view",
            "data": {"collection_id": collection_id, "view_id": view_id},
        }
        await self._agent.apply_blocks(caller, doc.id, [block])
        return doc

    async def import_file(
        self,
        caller: CallerContext,
        *,
        workspace_id: WorkspaceId,
        filename: str,
        content: bytes,
        parent_id: DocumentId | None = None,
    ) -> Document:
        """Create one private document from a single uploaded file."""
        blocks = self._extractor.extract_blocks(filename=filename, content=content)
        title = _title_from_blocks(blocks) or _filename_stem(filename)
        return await self._create_with_blocks(
            caller,
            workspace_id=workspace_id,
            title=title,
            blocks=blocks,
            parent_id=parent_id,
        )

    async def import_notion_zip(
        self,
        caller: CallerContext,
        *,
        workspace_id: WorkspaceId,
        content: bytes,
    ) -> list[Document]:
        """Create a document per `.md` in a Notion export, nested by folder."""
        created: list[Document] = []
        parents: dict[str, Document] = {}
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = sorted(
                info.filename
                for info in archive.infolist()
                if info.filename.lower().endswith(".md")
                and info.file_size <= _MAX_FILE_SIZE
            )
            for name in names[:_MAX_ENTRIES]:
                await self._import_zip_entry(
                    caller, workspace_id, archive, name, parents, created
                )
        return created

    async def _import_zip_entry(
        self,
        caller: CallerContext,
        workspace_id: WorkspaceId,
        archive: zipfile.ZipFile,
        name: str,
        parents: dict[str, Document],
        created: list[Document],
    ) -> None:
        path = PurePosixPath(name)
        parent = await self._ensure_parent_path(
            caller, workspace_id, path.parent, parents, created
        )
        blocks = self._extractor.extract_blocks(
            filename=name, content=archive.read(name)
        )
        doc = await self._create_with_blocks(
            caller,
            workspace_id=workspace_id,
            title=_notion_title(path.name),
            blocks=blocks,
            parent_id=parent.id if parent else None,
        )
        created.append(doc)

    async def _ensure_parent_path(
        self,
        caller: CallerContext,
        workspace_id: WorkspaceId,
        folder: PurePosixPath,
        parents: dict[str, Document],
        created: list[Document],
    ) -> Document | None:
        """Create/reuse a parent document per folder segment; return the deepest."""
        if str(folder) in (".", ""):
            return None
        parent: Document | None = None
        accumulated = ""
        for segment in folder.parts:
            accumulated = f"{accumulated}/{segment}" if accumulated else segment
            existing = parents.get(accumulated)
            if existing is None:
                existing = await self._create_with_blocks(
                    caller,
                    workspace_id=workspace_id,
                    title=_notion_title(segment),
                    blocks=[],
                    parent_id=parent.id if parent else None,
                )
                parents[accumulated] = existing
                created.append(existing)
            parent = existing
        return parent

    async def _create_with_blocks(
        self,
        caller: CallerContext,
        *,
        workspace_id: WorkspaceId,
        title: str,
        blocks: list[dict],
        parent_id: DocumentId | None,
    ) -> Document:
        doc = await self._documents.create(
            caller, workspace_id=workspace_id, title=title, parent_id=parent_id
        )
        if blocks:
            await self._agent.apply_blocks(caller, doc.id, blocks)
        return doc


def _title_from_blocks(blocks: list[dict]) -> str:
    """The first non-empty heading's text, capped, else ''."""
    for block in blocks:
        if block.get("type") == "heading":
            text = ((block.get("data") or {}).get("text") or "").strip()
            if text:
                return text[:_TITLE_LIMIT]
    return ""


def _filename_stem(filename: str) -> str:
    return PurePosixPath(filename).stem or filename or "Untitled"


def _notion_title(name: str) -> str:
    """A folder/file name with the `.md` suffix and Notion id stripped."""
    stem = PurePosixPath(name).stem
    return _NOTION_ID_RE.sub("", stem).strip() or "Untitled"


def _cell(row: list[str], index: int) -> str:
    """A row's cell at ``index``, or ``""`` when the row is short."""
    return row[index] if index < len(row) else ""


def _is_number(text: str) -> bool:
    try:
        float(text)
    except ValueError:
        return False
    return True


def _infer_column_type(rows: list[list[str]], index: int) -> PropertyType:
    """NUMBER when the column has at least one value and every non-empty value
    parses as a number; TEXT otherwise."""
    non_empty = [cell for row in rows if (cell := _cell(row, index))]
    if non_empty and all(_is_number(cell) for cell in non_empty):
        return PropertyType.NUMBER
    return PropertyType.TEXT
