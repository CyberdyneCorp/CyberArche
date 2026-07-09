"""Use cases: the application's capabilities, one module per capability."""

from __future__ import annotations

from dataclasses import dataclass

from cyberarche.application.use_cases.agent import AgentUseCases
from cyberarche.application.use_cases.api_keys import ApiKeyUseCases
from cyberarche.application.use_cases.connectors import ConnectorUseCases
from cyberarche.application.use_cases.documents import DocumentUseCases
from cyberarche.application.use_cases.files import FileUseCases
from cyberarche.application.use_cases.knowledge import KnowledgeUseCases
from cyberarche.application.use_cases.realtime import RealtimeUseCases
from cyberarche.application.use_cases.sharing import SharingUseCases
from cyberarche.application.use_cases.folders import FolderUseCases
from cyberarche.application.use_cases.teamspaces import (
    FavoriteUseCases,
    TeamspaceUseCases,
)
from cyberarche.application.use_cases.snapshots import SnapshotUseCases
from cyberarche.application.use_cases.workspaces import WorkspaceUseCases


@dataclass(frozen=True, slots=True)
class UseCases:
    """Aggregate handed to every inbound adapter (HTTP, MCP, workers)."""

    workspaces: WorkspaceUseCases
    documents: DocumentUseCases
    snapshots: SnapshotUseCases
    realtime: RealtimeUseCases
    knowledge: KnowledgeUseCases
    connectors: ConnectorUseCases
    agent: AgentUseCases
    sharing: SharingUseCases
    api_keys: ApiKeyUseCases
    teamspaces: TeamspaceUseCases
    favorites: FavoriteUseCases
    folders: FolderUseCases
    files: FileUseCases
