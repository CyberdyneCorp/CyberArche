"""File extraction port (ai-agent spec): uploaded files -> document blocks."""

from __future__ import annotations

from typing import Protocol


class FileExtractorPort(Protocol):
    def extract_blocks(self, *, filename: str, content: bytes) -> list[dict]:
        """Convert a file (PDF/CSV/XLSX/MD/TXT) into block dicts.

        Tabular sources (CSV/Excel) SHALL become `table` blocks whose rows
        and columns match the source sheet; text sources become paragraph/
        heading blocks. Raises ValidationFailed for unsupported types.
        """
        ...

    def extract_table(
        self, *, filename: str, content: bytes
    ) -> tuple[list[str], list[list[str]]]:
        """Parse a CSV/Excel sheet into ``(header, rows)`` for importing it as a
        collection: the first row is the header, the rest are data rows (empty
        input -> ``([], [])``). Raises ValidationFailed for non-spreadsheets.
        """
        ...
