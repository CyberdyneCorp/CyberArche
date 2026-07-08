"""Use cases: the application's capabilities, one module per capability."""

from __future__ import annotations

from dataclasses import dataclass

from cyberarche.application.use_cases.documents import DocumentUseCases
from cyberarche.application.use_cases.snapshots import SnapshotUseCases
from cyberarche.application.use_cases.workspaces import WorkspaceUseCases


@dataclass(frozen=True, slots=True)
class UseCases:
    """Aggregate handed to every inbound adapter (HTTP, MCP, workers)."""

    workspaces: WorkspaceUseCases
    documents: DocumentUseCases
    snapshots: SnapshotUseCases
