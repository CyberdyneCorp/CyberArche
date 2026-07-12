"""Page templates (templates spec): a saved block tree, reusable per workspace."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from cyberarche.domain.ids import TemplateId, TenantId, UserId, WorkspaceId


@dataclass(frozen=True, slots=True)
class Template:
    id: TemplateId
    tenant_id: TenantId
    workspace_id: WorkspaceId
    name: str
    created_by: UserId
    created_at: datetime
    content: list[dict[str, Any]] = field(default_factory=list)
