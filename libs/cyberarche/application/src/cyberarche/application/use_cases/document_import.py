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
from cyberarche.application.use_cases.documents import DocumentUseCases
from cyberarche.domain.documents import Document
from cyberarche.domain.ids import DocumentId, WorkspaceId

# Zip-bomb guards: a Notion export is a modest set of markdown files.
_MAX_ENTRIES = 2000
_MAX_FILE_SIZE = 5 * 1024 * 1024

_TITLE_LIMIT = 200
# Notion appends a space + 32-hex page id to every file and folder name.
_NOTION_ID_RE = re.compile(r"\s+[0-9a-fA-F]{32}$")


class ImportUseCases:
    def __init__(
        self,
        documents: DocumentUseCases,
        agent: AgentUseCases,
        extractor: FileExtractorPort,
        ids: IdPort,
    ) -> None:
        self._documents = documents
        self._agent = agent
        self._extractor = extractor
        self._ids = ids

    async def import_upload(
        self,
        caller: CallerContext,
        *,
        workspace_id: WorkspaceId,
        filename: str,
        content: bytes,
    ) -> list[Document]:
        """Dispatch by extension: `.zip` -> Notion export, else a single file."""
        if PurePosixPath(filename.lower()).suffix == ".zip":
            return await self.import_notion_zip(
                caller, workspace_id=workspace_id, content=content
            )
        doc = await self.import_file(
            caller, workspace_id=workspace_id, filename=filename, content=content
        )
        return [doc]

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
