"""document-model spec: workspace scenarios."""

from __future__ import annotations

from cyberarche.application.use_cases import UseCases
from cyberarche.domain.memberships import Role


async def test_create_workspace_grants_owner_to_creator(use_cases: UseCases, alice):
    workspace = await use_cases.workspaces.create(alice, name="Engineering")

    assert workspace.tenant_id == alice.tenant_id
    role = await use_cases.workspaces._memberships.workspace_role(
        workspace.id, alice.user_id
    )
    assert role is not None and role.role is Role.OWNER


async def test_workspaces_are_tenant_isolated(use_cases: UseCases, alice, bob_other_tenant):
    await use_cases.workspaces.create(alice, name="Acme Docs")

    assert await use_cases.workspaces.list(bob_other_tenant) == []
    mine = await use_cases.workspaces.list(alice)
    assert [w.name for w in mine] == ["Acme Docs"]
