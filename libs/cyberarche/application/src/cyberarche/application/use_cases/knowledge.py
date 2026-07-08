"""Knowledge use cases (rag-knowledge spec): ingestion and retrieval.

Every workspace maps 1:1 to an isolated CyberdyneRAG project, so tenant
isolation is inherited from the RAG service's per-project guarantee.
"""

from __future__ import annotations

import hashlib
from dataclasses import replace

from cyberarche.application.authz import AccessControl
from cyberarche.application.kernel import CallerContext
from cyberarche.application.ports.rag import (
    IngestionRecord,
    IngestionRepository,
    RagPort,
    RagQueryMode,
    RagTask,
    RagTaskStatus,
)
from cyberarche.application.ports.repositories import WorkspaceRepository
from cyberarche.application.ports.telemetry import ClockPort
from cyberarche.domain.errors import NotFound
from cyberarche.domain.ids import WorkspaceId
from cyberarche.domain.memberships import Role
from cyberarche.domain.workspaces import Workspace


def project_slug_for(workspace: Workspace) -> str:
    return f"ws-{workspace.id}"


class KnowledgeUseCases:
    def __init__(
        self,
        workspaces: WorkspaceRepository,
        ingestions: IngestionRepository,
        rag: RagPort,
        access: AccessControl,
        clock: ClockPort,
    ) -> None:
        self._workspaces = workspaces
        self._ingestions = ingestions
        self._rag = rag
        self._access = access
        self._clock = clock

    async def provision_project(
        self, caller: CallerContext, workspace_id: WorkspaceId
    ) -> Workspace:
        """Ensure the workspace's isolated RAG project exists (idempotent)."""
        workspace = await self._workspace(caller, workspace_id, Role.VIEWER)
        slug = workspace.rag_project_slug or project_slug_for(workspace)
        await self._rag.ensure_project(slug, name=workspace.name)
        if workspace.rag_project_slug != slug:
            workspace = workspace.with_rag_project(slug)
            await self._workspaces.update(workspace)
        return workspace

    async def ingest_file(
        self,
        caller: CallerContext,
        workspace_id: WorkspaceId,
        *,
        filename: str,
        content: bytes,
        content_type: str = "application/octet-stream",
        force: bool = False,
    ) -> IngestionRecord:
        """Upload a file to the workspace's RAG project and track its task.

        Content-hash dedupe: re-ingesting identical content returns the
        existing record instead of re-uploading (rag-knowledge spec).
        """
        await self._workspace(caller, workspace_id, Role.EDITOR)
        workspace = await self.provision_project(caller, workspace_id)
        content_hash = hashlib.sha256(content).hexdigest()
        if not force:
            existing = await self._ingestions.by_hash(workspace_id, content_hash)
            if existing is not None and existing.status is not RagTaskStatus.FAILED:
                return existing
        task = await self._rag.upload(
            workspace.rag_project_slug,
            filename=filename,
            content=content,
            content_type=content_type,
        )
        record = IngestionRecord(
            task_id=task.task_id,
            workspace_id=workspace_id,
            filename=filename,
            content_hash=content_hash,
            status=task.status,
            created_at=self._clock.now(),
        )
        await self._ingestions.add(record)
        return record

    async def refresh_task(
        self, caller: CallerContext, workspace_id: WorkspaceId, task_id: str
    ) -> IngestionRecord:
        """Poll the RAG task and persist its latest status."""
        workspace = await self._workspace(caller, workspace_id, Role.VIEWER)
        record = await self._ingestions.get(workspace_id, task_id)
        if record is None or not workspace.rag_project_slug:
            raise NotFound("ingestion task not found")
        task = await self._rag.task_status(workspace.rag_project_slug, task_id)
        return await self._apply_status(record, task)

    async def complete_from_webhook(self, task_id: str, *, status: str, error: str | None) -> None:
        """Callback path: the RAG service reports task completion."""
        record = await self._ingestions.by_task_id(task_id)
        if record is None:
            raise NotFound("unknown ingestion task")
        task = RagTask(task_id=task_id, status=RagTaskStatus(status), error=error)
        await self._apply_status(record, task)

    async def query(
        self,
        caller: CallerContext,
        workspace_id: WorkspaceId,
        *,
        query: str,
        mode: RagQueryMode = RagQueryMode.HYBRID,
    ) -> str:
        """Retrieval over this workspace's isolated project only."""
        workspace = await self._workspace(caller, workspace_id, Role.VIEWER)
        if not workspace.rag_project_slug:
            raise NotFound("workspace has no knowledge base yet")
        return await self._rag.query(workspace.rag_project_slug, query=query, mode=mode)

    async def list_sources(
        self, caller: CallerContext, workspace_id: WorkspaceId
    ) -> list[IngestionRecord]:
        await self._workspace(caller, workspace_id, Role.VIEWER)
        return await self._ingestions.list_for_workspace(workspace_id)

    async def delete_source(
        self, caller: CallerContext, workspace_id: WorkspaceId, *, filename: str
    ) -> None:
        """Delete cascades to the RAG datasource (rag-knowledge spec)."""
        workspace = await self._workspace(caller, workspace_id, Role.EDITOR)
        if workspace.rag_project_slug:
            await self._rag.delete_datasource(workspace.rag_project_slug, filename)
        await self._ingestions.delete_by_filename(workspace_id, filename)

    async def _apply_status(
        self, record: IngestionRecord, task: RagTask
    ) -> IngestionRecord:
        if task.status is record.status and task.error == record.error:
            return record
        updated = replace(record, status=task.status, error=task.error)
        await self._ingestions.update(updated)
        return updated

    async def _workspace(
        self, caller: CallerContext, workspace_id: WorkspaceId, role: Role
    ) -> Workspace:
        workspace = await self._workspaces.get(caller.tenant_id, workspace_id)
        if workspace is None:
            raise NotFound("workspace not found")
        await self._access.require_workspace(caller, workspace_id, role)
        return workspace
