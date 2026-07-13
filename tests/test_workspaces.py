"""document-model spec: workspace scenarios."""

from __future__ import annotations

import pytest

from cyberarche.application.testing.fakes import (
    FixedClock,
    InMemoryMembershipRepository,
    InMemoryRag,
    InMemoryWorkspaceRepository,
    SequentialIds,
)
from cyberarche.application.use_cases import UseCases
from cyberarche.application.use_cases.workspaces import WorkspaceUseCases
from cyberarche.domain.errors import NotFound
from cyberarche.domain.ids import WorkspaceId
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


async def test_get_returns_the_workspace(use_cases: UseCases, alice):
    workspace = await use_cases.workspaces.create(alice, name="Docs")

    got = await use_cases.workspaces.get(alice, workspace.id)
    assert got.id == workspace.id and got.name == "Docs"


async def test_get_missing_workspace_raises_not_found(use_cases: UseCases, alice):
    with pytest.raises(NotFound):
        await use_cases.workspaces.get(alice, WorkspaceId("nope"))


async def test_get_is_tenant_isolated(use_cases: UseCases, alice, bob_other_tenant):
    workspace = await use_cases.workspaces.create(alice, name="Acme Docs")

    with pytest.raises(NotFound):
        await use_cases.workspaces.get(bob_other_tenant, workspace.id)


async def test_create_provisions_an_isolated_rag_project(use_cases: UseCases, rag, alice):
    workspace = await use_cases.workspaces.create(alice, name="Docs")

    assert workspace.rag_project_slug is not None
    assert workspace.rag_project_slug in rag.projects


async def test_create_without_rag_leaves_slug_unset(alice):
    workspaces = WorkspaceUseCases(
        InMemoryWorkspaceRepository(),
        InMemoryMembershipRepository(),
        FixedClock(),
        SequentialIds(),
        rag=None,
    )

    workspace = await workspaces.create(alice, name="No RAG")

    assert workspace.rag_project_slug is None
    stored = await workspaces.get(alice, workspace.id)
    assert stored.rag_project_slug is None


class _FailingRag(InMemoryRag):
    async def ensure_project(self, slug: str, *, name: str) -> None:
        raise RuntimeError("provider down")


async def test_rag_provider_outage_defers_provisioning(alice):
    """A RAG outage must not block workspace creation (rag-knowledge spec):
    the workspace is created, the slug stays unset, and ownership is granted."""
    memberships = InMemoryMembershipRepository()
    workspaces = WorkspaceUseCases(
        InMemoryWorkspaceRepository(),
        memberships,
        FixedClock(),
        SequentialIds(),
        rag=_FailingRag(),
    )

    workspace = await workspaces.create(alice, name="Deferred")

    assert workspace.rag_project_slug is None
    role = await memberships.workspace_role(workspace.id, alice.user_id)
    assert role is not None and role.role is Role.OWNER
