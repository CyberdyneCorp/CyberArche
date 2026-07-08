"""Workspace use cases (document-model spec)."""

from __future__ import annotations

import logging

from cyberarche.application.kernel import CallerContext
from cyberarche.application.ports.rag import RagPort
from cyberarche.application.ports.repositories import (
    MembershipRepository,
    WorkspaceRepository,
)
from cyberarche.application.ports.telemetry import ClockPort, IdPort
from cyberarche.domain.errors import NotFound
from cyberarche.domain.ids import WorkspaceId
from cyberarche.domain.memberships import Role, WorkspaceMembership
from cyberarche.domain.workspaces import Workspace

logger = logging.getLogger(__name__)


class WorkspaceUseCases:
    def __init__(
        self,
        workspaces: WorkspaceRepository,
        memberships: MembershipRepository,
        clock: ClockPort,
        ids: IdPort,
        rag: RagPort | None = None,
    ) -> None:
        self._workspaces = workspaces
        self._memberships = memberships
        self._clock = clock
        self._ids = ids
        self._rag = rag

    async def create(self, caller: CallerContext, *, name: str) -> Workspace:
        """Create a workspace in the caller's tenant; creator becomes owner.

        An isolated RAG project is provisioned best-effort (rag-knowledge
        spec); on provider failure the slug stays unset and is retried on
        first knowledge use.
        """
        now = self._clock.now()
        workspace = Workspace.create(
            id=WorkspaceId(self._ids.new_id()),
            tenant_id=caller.tenant_id,
            name=name,
            created_by=caller.user_id,
            created_at=now,
        )
        workspace = await self._provision_rag(workspace)
        await self._workspaces.add(workspace)
        await self._memberships.add_workspace_member(
            WorkspaceMembership(
                workspace_id=workspace.id,
                user_id=caller.user_id,
                role=Role.OWNER,
                granted_at=now,
            )
        )
        return workspace

    async def list(self, caller: CallerContext) -> list[Workspace]:
        """Only workspaces of the caller's tenant (tenant isolation)."""
        return await self._workspaces.list_for_tenant(caller.tenant_id)

    async def get(self, caller: CallerContext, workspace_id: WorkspaceId) -> Workspace:
        workspace = await self._workspaces.get(caller.tenant_id, workspace_id)
        if workspace is None:
            raise NotFound("workspace not found")
        return workspace

    async def _provision_rag(self, workspace: Workspace) -> Workspace:
        if self._rag is None:
            return workspace
        from cyberarche.application.use_cases.knowledge import project_slug_for

        slug = project_slug_for(workspace)
        try:
            await self._rag.ensure_project(slug, name=workspace.name)
        except Exception:  # provider outage must not block workspace creation
            logger.warning("RAG project provisioning deferred for %s", workspace.id)
            return workspace
        return workspace.with_rag_project(slug)
