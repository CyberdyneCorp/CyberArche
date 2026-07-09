"""External MCP connector aggregate (external-mcp-connectors spec)."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import datetime

from cyberarche.domain.errors import ValidationFailed
from cyberarche.domain.ids import (
    ConnectorId,
    DocumentId,
    TenantId,
    UserId,
    WorkspaceId,
)

# Separator between connector namespace and tool name; both sides must be
# valid MCP/LLM tool-name characters ([a-zA-Z0-9_-]).
NAMESPACE_SEPARATOR = "__"

_SLUG_RE = re.compile(r"[^a-z0-9-]+")


def slugify(name: str) -> str:
    slug = _SLUG_RE.sub("-", name.strip().lower()).strip("-")
    if not slug:
        raise ValidationFailed("connector name must contain letters or digits")
    return slug


@dataclass(frozen=True, slots=True)
class Connector:
    id: ConnectorId
    tenant_id: TenantId
    workspace_id: WorkspaceId
    name: str  # display name
    slug: str  # namespace prefix for its tools
    endpoint: str
    enabled: bool
    created_by: UserId
    created_at: datetime
    # None = workspace-scoped (active on every document); otherwise active only
    # when the agent is working on this document.
    document_id: DocumentId | None = None

    def active_for(self, document_id: DocumentId) -> bool:
        return self.document_id is None or self.document_id == document_id

    def qualified(self, tool_name: str) -> str:
        return f"{self.slug}{NAMESPACE_SEPARATOR}{tool_name}"

    def set_enabled(self, enabled: bool) -> "Connector":
        return replace(self, enabled=enabled)


def split_qualified(qualified_name: str) -> tuple[str, str] | None:
    """(connector_slug, tool_name) if the name is connector-qualified."""
    slug, separator, tool = qualified_name.partition(NAMESPACE_SEPARATOR)
    if not separator or not slug or not tool:
        return None
    return slug, tool
