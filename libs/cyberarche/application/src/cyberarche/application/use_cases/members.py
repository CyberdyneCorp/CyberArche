"""Workspace member administration (workspace-members spec).

Listing is open to any member; mutations are owner-gated. Every mutation
path — including the invite upsert in SharingUseCases — must keep at least
one owner, so a workspace can never become ownerless.
"""

from __future__ import annotations

from dataclasses import dataclass

from cyberarche.application.authz import AccessControl
from cyberarche.application.kernel import CallerContext
from cyberarche.application.ports.identity import DirectoryPort, DirectoryUser
from cyberarche.application.ports.repositories import MembershipRepository
from cyberarche.application.ports.telemetry import ClockPort
from cyberarche.application.use_cases.org_directory import has_org
from cyberarche.domain.errors import Conflict, NotFound, UpstreamUnavailable
from cyberarche.domain.ids import UserId, WorkspaceId
from cyberarche.domain.memberships import Role, WorkspaceMembership

_ENRICH_PAGE_SIZE = 200
_ENRICH_MAX_PAGES = 10


@dataclass(frozen=True, slots=True)
class WorkspaceMember:
    """A membership enriched (best-effort) with directory identity."""

    membership: WorkspaceMembership
    email: str | None = None
    avatar_url: str | None = None


async def ensure_another_owner(
    memberships: MembershipRepository, workspace_id: WorkspaceId, user_id: UserId
) -> None:
    """Reject demoting/removing `user_id` if no other owner would remain."""
    members = await memberships.list_workspace_members(workspace_id)
    others = [
        m for m in members if m.role == Role.OWNER and str(m.user_id) != str(user_id)
    ]
    if not others:
        raise Conflict("a workspace must keep at least one owner")


class WorkspaceMemberUseCases:
    def __init__(
        self,
        memberships: MembershipRepository,
        access: AccessControl,
        clock: ClockPort,
        directory: DirectoryPort | None = None,
    ) -> None:
        self._memberships = memberships
        self._access = access
        self._clock = clock
        self._directory = directory

    async def list_members(
        self, caller: CallerContext, workspace_id: WorkspaceId
    ) -> list[WorkspaceMember]:
        await self._access.require_workspace(caller, workspace_id, Role.VIEWER)
        members = await self._memberships.list_workspace_members(workspace_id)
        index = await self._directory_index(caller)
        enriched = []
        for membership in members:
            user = index.get(str(membership.user_id))
            enriched.append(
                WorkspaceMember(
                    membership=membership,
                    email=user.email if user else None,
                    avatar_url=user.avatar_url if user else None,
                )
            )
        return enriched

    async def set_member_role(
        self,
        caller: CallerContext,
        workspace_id: WorkspaceId,
        *,
        user_id: UserId,
        role: Role,
    ) -> WorkspaceMembership:
        await self._access.require_workspace(caller, workspace_id, Role.OWNER)
        current = await self._membership_or_404(workspace_id, user_id)
        if current.role == Role.OWNER and role != Role.OWNER:
            await ensure_another_owner(self._memberships, workspace_id, user_id)
        updated = WorkspaceMembership(
            workspace_id=workspace_id,
            user_id=user_id,
            role=role,
            granted_at=self._clock.now(),
        )
        await self._memberships.add_workspace_member(updated)
        return updated

    async def remove_member(
        self, caller: CallerContext, workspace_id: WorkspaceId, user_id: UserId
    ) -> None:
        await self._access.require_workspace(caller, workspace_id, Role.OWNER)
        current = await self._membership_or_404(workspace_id, user_id)
        if current.role == Role.OWNER:
            await ensure_another_owner(self._memberships, workspace_id, user_id)
        await self._memberships.remove_workspace_member(workspace_id, user_id)

    async def _membership_or_404(
        self, workspace_id: WorkspaceId, user_id: UserId
    ) -> WorkspaceMembership:
        membership = await self._memberships.workspace_role(workspace_id, user_id)
        if membership is None:
            raise NotFound("member not found")
        return membership

    async def _directory_index(
        self, caller: CallerContext
    ) -> dict[str, DirectoryUser]:
        """Id -> directory identity for the caller's org; empty on any failure
        (enrichment is best-effort, never a reason to fail the listing)."""
        if self._directory is None or not has_org(caller):
            return {}
        index: dict[str, DirectoryUser] = {}
        try:
            for page in range(1, _ENRICH_MAX_PAGES + 1):
                result = await self._directory.list_org_users(
                    str(caller.tenant_id), page=page, page_size=_ENRICH_PAGE_SIZE
                )
                index.update({user.id: user for user in result.users})
                if not result.users or len(index) >= result.total:
                    break
        except UpstreamUnavailable:
            return {}
        return index
