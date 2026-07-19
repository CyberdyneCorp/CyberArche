"""Pure GitHub-flavored-markdown -> block-dict converter (document-import spec).

Turns markdown text into the same `{"id", "type", "data"}` block dicts the rest
of the system uses (see `blocks.BLOCK_TYPES`). It is deliberately dependency-free
— the caller passes a `new_id` callable (typically `ids.new_id`) so the domain
does not depend on any port. The block shapes mirror the agent's line-based
parser and the file extractor's table/image blocks exactly, so imported content
renders like agent- or upload-produced content.
"""

from __future__ import annotations

import re
from typing import Callable

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_QUOTE_RE = re.compile(r"^>\s?(.*)$")
_TODO_RE = re.compile(r"^[-*+]\s+\[([ xX])\]\s+(.*)$")
_BULLET_RE = re.compile(r"^[-*+]\s+(.*)$")
_NUMBERED_RE = re.compile(r"^\d+[.)]\s+(.*)$")
_IMAGE_RE = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)$")
# A GFM table separator row, e.g. `| --- | :--: |` (dashes with optional colons).
_TABLE_SEP_RE = re.compile(r"^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?$")

NewId = Callable[[], str]


def markdown_to_blocks(text: str, new_id: NewId) -> list[dict]:
    """Convert GitHub-flavored markdown into an ordered list of block dicts."""
    lines = text.split("\n")
    blocks: list[dict] = []
    paragraph: list[str] = []
    i = 0
    while i < len(lines):
        consumed = _consume_multiline(lines, i, new_id)
        if consumed is not None:
            block, i = consumed
            _flush_paragraph(paragraph, new_id, blocks)
            blocks.append(block)
        else:
            _consume_line(lines[i], new_id, paragraph, blocks)
            i += 1
    _flush_paragraph(paragraph, new_id, blocks)
    return blocks


def _consume_line(
    line: str, new_id: NewId, paragraph: list[str], blocks: list[dict]
) -> None:
    """Handle one single-line unit (blank, block-level line, or prose)."""
    stripped = line.strip()
    if not stripped:
        _flush_paragraph(paragraph, new_id, blocks)
        return
    block = _block_from_line(stripped, new_id)
    if block is not None:
        _flush_paragraph(paragraph, new_id, blocks)
        blocks.append(block)
    else:
        paragraph.append(line)


def _consume_multiline(
    lines: list[str], i: int, new_id: NewId
) -> tuple[dict, int] | None:
    """Consume a fenced code block, GFM table, or blockquote starting at line i.

    Returns the produced block and the index of the next unconsumed line, or
    None when line i does not begin a multi-line construct.
    """
    stripped = lines[i].strip()
    if stripped.startswith("```"):
        return _consume_fence(lines, i, new_id)
    if _is_table_start(lines, i):
        return _consume_table(lines, i, new_id)
    if _QUOTE_RE.match(stripped):
        return _consume_quote(lines, i, new_id)
    return None


def _consume_fence(lines: list[str], i: int, new_id: NewId) -> tuple[dict, int]:
    lang = lines[i].strip()[3:].strip().lower()
    body: list[str] = []
    j = i + 1
    while j < len(lines) and not lines[j].strip().startswith("```"):
        body.append(lines[j])
        j += 1
    j += 1  # skip the closing fence (or step past EOF)
    source = "\n".join(body)
    if lang == "mermaid":
        return _block("mermaid", {"source": source}, new_id), j
    return _block("code", {"source": source, "language": lang or "text"}, new_id), j


def _consume_table(lines: list[str], i: int, new_id: NewId) -> tuple[dict, int]:
    header = _split_row(lines[i])
    rows: list[list[str]] = []
    j = i + 2  # skip header + separator
    while j < len(lines) and lines[j].strip() and "|" in lines[j]:
        rows.append(_split_row(lines[j]))
        j += 1
    data = {"header": header, "rows": rows, "source": "markdown"}
    return _block("table", data, new_id), j


def _consume_quote(lines: list[str], i: int, new_id: NewId) -> tuple[dict, int]:
    texts: list[str] = []
    j = i
    while j < len(lines):
        match = _QUOTE_RE.match(lines[j].strip())
        if match is None:
            break
        texts.append(match.group(1).strip())
        j += 1
    return _block("quote", {"text": "\n".join(texts).strip()}, new_id), j


def _block_from_line(line: str, new_id: NewId) -> dict | None:
    """Map one stripped line to a single-line block, or None for prose."""
    heading = _HEADING_RE.match(line)
    if heading:
        text, level = heading.group(2).strip(), len(heading.group(1))
        return _block("heading", {"text": text, "level": level}, new_id)
    if line in ("---", "***", "___"):
        return _block("divider", {}, new_id)
    image = _IMAGE_RE.match(line)
    if image:
        return _block("image", {"url": image.group(2).strip(), "alt": image.group(1).strip()}, new_id)
    todo = _TODO_RE.match(line)  # before bullet: "- [ ] x" also matches _BULLET_RE
    if todo:
        checked = todo.group(1).lower() == "x"
        return _block("todo", {"text": todo.group(2).strip(), "checked": checked}, new_id)
    bullet = _BULLET_RE.match(line)
    if bullet:
        return _block("bulleted_list", {"text": bullet.group(1).strip()}, new_id)
    numbered = _NUMBERED_RE.match(line)
    if numbered:
        return _block("numbered_list", {"text": numbered.group(1).strip()}, new_id)
    return None


def _is_table_start(lines: list[str], i: int) -> bool:
    """A header row at line i followed by a `| --- | --- |` separator row."""
    if i + 1 >= len(lines) or "|" not in lines[i]:
        return False
    separator = lines[i + 1].strip()
    return "-" in separator and bool(_TABLE_SEP_RE.match(separator))


def _split_row(line: str) -> list[str]:
    """Split a `| a | b |` table row into stripped cells."""
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _flush_paragraph(paragraph: list[str], new_id: NewId, blocks: list[dict]) -> None:
    """Emit the buffered prose lines as one paragraph block, then clear them."""
    text = "\n".join(paragraph).strip()
    paragraph.clear()
    if text:
        blocks.append(_block("paragraph", {"text": text}, new_id))


def _block(block_type: str, data: dict, new_id: NewId) -> dict:
    return {"id": new_id(), "type": block_type, "data": data}
