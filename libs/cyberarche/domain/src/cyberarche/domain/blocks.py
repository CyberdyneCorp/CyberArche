"""Block model: a document body is an ordered tree of typed blocks.

The canonical content lives in the document CRDT; the domain owns the
block-type whitelist and the snapshot-side value objects.

Extensibility (architecture-quality spec): new block types are added by
registering them here — the editor engine, CRDT sync, and persistence do
not change per block type.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from cyberarche.domain.errors import ValidationFailed
from cyberarche.domain.ids import BlockId

# Registry of supported block types (document-model spec).
BLOCK_TYPES: frozenset[str] = frozenset(
    {
        "paragraph",
        "heading",
        "bulleted_list",
        "numbered_list",
        "todo",
        "callout",
        "quote",
        "divider",
        "code",
        "table",
        "latex",
        "mermaid",
        "whiteboard",
        "image",
        "file",
        "embed",
        "ai_block",
    }
)


def validate_block_type(block_type: str) -> str:
    if block_type not in BLOCK_TYPES:
        raise ValidationFailed(f"unknown block type: {block_type!r}")
    return block_type


@dataclass(frozen=True, slots=True)
class Block:
    """A snapshot-side block value object (the live tree lives in the CRDT)."""

    id: BlockId
    type: str
    data: dict[str, Any] = field(default_factory=dict)
    children: tuple["Block", ...] = ()

    def __post_init__(self) -> None:
        validate_block_type(self.type)
