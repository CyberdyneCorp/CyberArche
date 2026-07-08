"""Role resolution and permission checks used by every use case.

Enforcement lives here — in the application layer — so HTTP, realtime,
and MCP inbound adapters cannot diverge (permissions-sharing spec).
"""

from __future__ import annotations

from cyberarche.application.kernel import CallerContext
from cyberarche.application.ports.repositories import MembershipRepository
from cyberarche.application.ports.teamspaces import TeamspaceRepository
from cyberarche.domain.documents import Document
from cyberarche.domain.errors import NotAuthorized
from cyberarche.domain.ids import TeamspaceId, WorkspaceId
from cyberarche.domain.memberships import Role, effective_role, role_at_least, strongest
from cyberarche.domain.teamspaces import Teamspace


class AccessControl:
    def __init__(
        self,
        memberships: MembershipRepository,
        teamspaces: TeamspaceRepository | None = None,
    ) -> None:
        self._memberships = memberships
        self._teamspaces = teamspaces

    async def workspace_role(
        self, caller: CallerContext, workspace_id: WorkspaceId
    ) -> Role | None:
        membership = await self._memberships.workspace_role(workspace_id, caller.user_id)
        return membership.role if membership else None

    async def require_workspace(
        self, caller: CallerContext, workspace_id: WorkspaceId, required: Role
    ) -> Role:
        role = await self.workspace_role(caller, workspace_id)
        if role is None or not role_at_least(role, required):
            raise NotAuthorized(f"requires {required.value} on workspace")
        return role

    async def teamspace_role(
        self, caller: CallerContext, teamspace_id: TeamspaceId
    ) -> Role | None:
        if self._teamspaces is None:
            return None
        membership = await self._teamspaces.member_role(teamspace_id, caller.user_id)
        return membership.role if membership else None

    async def require_teamspace(
        self, caller: CallerContext, teamspace: Teamspace, required: Role
    ) -> Role:
        """Teamspace owners/members act within it; workspace owners always may."""
        role = strongest(
            await self.teamspace_role(caller, teamspace.id),
            await self.workspace_role(caller, teamspace.workspace_id),
        )
        if role is None or not role_at_least(role, required):
            raise NotAuthorized(f"requires {required.value} on teamspace")
        return role

    async def document_role(
        self, caller: CallerContext, document: Document
    ) -> Role | None:
        """Strongest of workspace and teamspace roles; a document-level grant
        overrides both (it may deliberately demote) — see design D-1."""
        workspace_role = await self.workspace_role(caller, document.workspace_id)
        teamspace_role = (
            await self.teamspace_role(caller, document.teamspace_id)
            if document.teamspace_id
            else None
        )
        grant = await self._memberships.document_grant(document.id, caller.user_id)
        return effective_role(
            workspace_role, grant.role if grant else None, teamspace_role
        )

    async def require_document(
        self, caller: CallerContext, document: Document, required: Role
    ) -> Role:
        role = await self.document_role(caller, document)
        if role is None or not role_at_least(role, required):
            raise NotAuthorized(f"requires {required.value} on document")
        return role
