"""Agent persona + memory domain (ai-agent spec).

Two tenant-isolated records shape the agent across conversations:
`CustomInstructions` (a workspace "house style", plus an optional per-user
layer) and `AgentMemory` (a durable note recalled in later runs). The
secret-pattern guard keeps obvious credentials out of stored memory.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from cyberarche.domain.ids import (
    AgentMemoryId,
    CustomInstructionsId,
    TenantId,
    UserId,
    WorkspaceId,
)


@dataclass(frozen=True, slots=True)
class CustomInstructions:
    """A workspace's agent instructions. `user_id` None = the shared workspace
    layer; a value = a personal layer visible only to that user."""

    id: CustomInstructionsId
    tenant_id: TenantId
    workspace_id: WorkspaceId
    user_id: UserId | None
    instructions: str
    updated_by: UserId
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class AgentMemory:
    """A durable note the agent recalls, scoped to a workspace."""

    id: AgentMemoryId
    tenant_id: TenantId
    workspace_id: WorkspaceId
    text: str
    created_by: UserId
    created_at: datetime
    updated_at: datetime


# Obvious credential shapes we refuse to persist into memory (D-5). This is a
# guard, not a scanner: it blocks the common leak patterns a model might echo.
_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),  # OpenAI-style keys
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS access key id
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),  # PEM private keys
    re.compile(r"\bghp_[A-Za-z0-9]{20,}"),  # GitHub PAT
    re.compile(r"\bcak_[A-Za-z0-9]{20,}"),  # CyberArche API key
    re.compile(r"(?i)\b(?:password|passwd|secret|api[_-]?key|token)\s*[:=]\s*\S+"),
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),  # JWT
)


def looks_like_secret(text: str) -> bool:
    """True if `text` contains an obvious credential and must not be stored."""
    return any(pattern.search(text) for pattern in _SECRET_PATTERNS)
