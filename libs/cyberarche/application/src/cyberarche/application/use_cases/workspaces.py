"""Workspace use cases (document-model spec)."""

from __future__ import annotations

from cyberarche.application.kernel import CallerContext
from cyberarche.application.ports.repositories import (
    MembershipRepository,
    WorkspaceRepository,
)
from cyberarche.application.ports.telemetry import ClockPort, IdPort
from cyberarche.domain.errors import NotFound
from cyberarche.domain.ids import WorkspaceId
from cyberarche.domain.memberships import Role, WorkspaceMembership
from cyberarche.domain.workspaces import Workspace


class WorkspaceUseCases:
    def __init__(
        self,
        workspaces: WorkspaceRepository,
        memberships: MembershipRepository,
        clock: ClockPort,
        ids: IdPort,
    ) -> None:
        self._workspaces = workspaces
        self._memberships = memberships
        self._clock = clock
        self._ids = ids

    async def create(self, caller: CallerContext, *, name: str) -> Workspace:
        """Create a workspace in the caller's tenant; creator becomes owner."""
        now = self._clock.now()
        workspace = Workspace.create(
            id=WorkspaceId(self._ids.new_id()),
            tenant_id=caller.tenant_id,
            name=name,
            created_by=caller.user_id,
            created_at=now,
        )
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
