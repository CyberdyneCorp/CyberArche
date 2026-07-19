"""Org directory use cases (org-directory spec).

The organization is always the caller's own tenant, resolved from verified
claims — a caller can never enumerate another organization.
"""

from __future__ import annotations

from cyberarche.application.kernel import CallerContext
from cyberarche.application.ports.identity import DirectoryPage, DirectoryPort
from cyberarche.domain.errors import UpstreamUnavailable


def has_org(caller: CallerContext) -> bool:
    """A personal tenant (tenant == subject) has no organization directory."""
    return str(caller.tenant_id) != str(caller.user_id)


class OrgDirectoryUseCases:
    def __init__(self, directory: DirectoryPort | None) -> None:
        self._directory = directory

    async def list_org_users(
        self,
        caller: CallerContext,
        *,
        search: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> DirectoryPage:
        if not has_org(caller):
            return DirectoryPage(users=[], total=0, page=page, page_size=page_size)
        if self._directory is None:
            raise UpstreamUnavailable("user directory is not configured")
        return await self._directory.list_org_users(
            str(caller.tenant_id), search=search, page=page, page_size=page_size
        )
