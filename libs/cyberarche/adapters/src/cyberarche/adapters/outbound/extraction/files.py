"""FileExtractorPort adapter: PDF (pypdf), Excel (openpyxl), CSV, text.

Tabular sources become `table` blocks (rows/columns match the sheet);
text sources become paragraph blocks (ai-agent + block-editor specs).
"""

from __future__ import annotations

import csv
import io
import uuid
from pathlib import PurePosixPath

from openpyxl import load_workbook
from pypdf import PdfReader

from cyberarche.domain.errors import ValidationFailed


def _block(block_type: str, data: dict) -> dict:
    return {"id": uuid.uuid4().hex, "type": block_type, "data": data}


def _table_block(rows: list[list[str]], *, source: str) -> dict:
    header, body = (rows[0], rows[1:]) if rows else ([], [])
    return _block(
        "table",
        {"header": header, "rows": body, "source": source},
    )


def _paragraphs(text: str) -> list[dict]:
    chunks = [chunk.strip() for chunk in text.split("\n\n")]
    return [_block("paragraph", {"text": chunk}) for chunk in chunks if chunk]


class FileExtractor:
    def extract_blocks(self, *, filename: str, content: bytes) -> list[dict]:
        suffix = PurePosixPath(filename.lower()).suffix
        if suffix == ".pdf":
            return self._pdf(content)
        if suffix == ".csv":
            return self._csv(content, filename)
        if suffix in (".xlsx", ".xlsm"):
            return self._excel(content, filename)
        if suffix in (".txt", ".md", ""):
            return _paragraphs(content.decode("utf-8", errors="replace"))
        raise ValidationFailed(f"unsupported file type: {suffix}")

    def _pdf(self, content: bytes) -> list[dict]:
        reader = PdfReader(io.BytesIO(content))
        blocks: list[dict] = []
        for page in reader.pages:
            blocks.extend(_paragraphs(page.extract_text() or ""))
        return blocks

    def _csv(self, content: bytes, filename: str) -> list[dict]:
        text = content.decode("utf-8-sig", errors="replace")
        rows = [row for row in csv.reader(io.StringIO(text)) if row]
        if not rows:
            return []
        return [_table_block(rows, source=filename)]

    def _excel(self, content: bytes, filename: str) -> list[dict]:
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        blocks: list[dict] = []
        for sheet in workbook.worksheets:
            rows = _sheet_rows(sheet)
            if not rows:
                continue
            blocks.append(_block("heading", {"text": sheet.title, "level": 2}))
            blocks.append(_table_block(rows, source=f"{filename}#{sheet.title}"))
        return blocks


def _sheet_rows(sheet) -> list[list[str]]:
    return [
        ["" if cell is None else str(cell) for cell in row]
        for row in sheet.iter_rows(values_only=True)
        if any(cell is not None for cell in row)
    ]
