"""Postgres persona/memory adapters: SQL parameters and row mapping.

These repositories are thin SQL shims, so the unit seam is the pool itself:
a scripted fake records every (method, query, args) call and returns dict
rows (asyncpg.Record is mapping-like, so plain dicts stand in). Behavioral
contracts against a real database live in test_port_contracts.py.
"""

from __future__ import annotations

from datetime import UTC, datetime

from cyberarche.adapters.outbound.postgres.agent_memory import (
    PostgresAgentMemoryRepository,
    PostgresCustomInstructionsRepository,
    _tokens,
)
from cyberarche.domain.agent_persona import AgentMemory, CustomInstructions
from cyberarche.domain.ids import (
    AgentMemoryId,
    CustomInstructionsId,
    TenantId,
    UserId,
    WorkspaceId,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


class FakePool:
    """Scripted asyncpg.Pool: records calls, returns canned rows."""

    def __init__(self, rows: list[dict] | None = None, row: dict | None = None):
        self.rows = rows or []
        self.row = row
        self.calls: list[tuple[str, str, tuple]] = []

    async def fetch(self, query: str, *args) -> list[dict]:
        self.calls.append(("fetch", query, args))
        return self.rows

    async def fetchrow(self, query: str, *args) -> dict | None:
        self.calls.append(("fetchrow", query, args))
        return self.row

    async def execute(self, query: str, *args) -> None:
        self.calls.append(("execute", query, args))


def instructions_row(user_id: str | None = None) -> dict:
    return {
        "id": "ci-1",
        "tenant_id": "acme",
        "workspace_id": "ws-1",
        "user_id": user_id,
        "instructions": "Be terse.",
        "updated_by": "alice",
        "updated_at": NOW,
    }


def memory_row(memory_id: str = "mem-1", text: str = "Prefers dark mode") -> dict:
    return {
        "id": memory_id,
        "tenant_id": "acme",
        "workspace_id": "ws-1",
        "text": text,
        "created_by": "alice",
        "created_at": NOW,
        "updated_at": NOW,
    }


def memory(memory_id: str = "mem-1", text: str = "Prefers dark mode") -> AgentMemory:
    return AgentMemory(
        id=AgentMemoryId(memory_id),
        tenant_id=TenantId("acme"),
        workspace_id=WorkspaceId("ws-1"),
        text=text,
        created_by=UserId("alice"),
        created_at=NOW,
        updated_at=NOW,
    )


# --- _tokens: keyword extraction for recall matching -------------------------


def test_tokens_lowercases_strips_punctuation_and_dedupes():
    assert _tokens("Dark-Mode, dark mode! DARK") == ["darkmode", "dark", "mode"]


def test_tokens_drops_short_tokens():
    # "of", "a", and the punctuation-only word all fall under the 3-char floor.
    assert _tokens("of a :: the API") == ["the", "api"]


def test_tokens_empty_query_yields_nothing():
    assert _tokens("") == []
    assert _tokens("  a b !! ") == []


# --- PostgresCustomInstructionsRepository ------------------------------------


async def test_instructions_get_maps_workspace_layer_row():
    pool = FakePool(row=instructions_row(user_id=None))
    repo = PostgresCustomInstructionsRepository(pool)

    record = await repo.get(TenantId("acme"), WorkspaceId("ws-1"), None)

    assert record == CustomInstructions(
        id=CustomInstructionsId("ci-1"),
        tenant_id=TenantId("acme"),
        workspace_id=WorkspaceId("ws-1"),
        user_id=None,
        instructions="Be terse.",
        updated_by=UserId("alice"),
        updated_at=NOW,
    )
    method, query, args = pool.calls[0]
    assert method == "fetchrow"
    assert "agent_custom_instructions" in query
    assert args == ("acme", "ws-1", None)


async def test_instructions_get_maps_personal_layer_user_id():
    pool = FakePool(row=instructions_row(user_id="bob"))
    repo = PostgresCustomInstructionsRepository(pool)

    record = await repo.get(TenantId("acme"), WorkspaceId("ws-1"), UserId("bob"))

    assert record is not None
    assert record.user_id == UserId("bob")
    assert pool.calls[0][2] == ("acme", "ws-1", "bob")


async def test_instructions_get_returns_none_when_missing():
    pool = FakePool(row=None)
    repo = PostgresCustomInstructionsRepository(pool)

    assert await repo.get(TenantId("acme"), WorkspaceId("ws-1"), None) is None


async def test_instructions_upsert_passes_all_fields():
    pool = FakePool()
    repo = PostgresCustomInstructionsRepository(pool)
    record = CustomInstructions(
        id=CustomInstructionsId("ci-1"),
        tenant_id=TenantId("acme"),
        workspace_id=WorkspaceId("ws-1"),
        user_id=UserId("bob"),
        instructions="Be terse.",
        updated_by=UserId("bob"),
        updated_at=NOW,
    )

    await repo.upsert(record)

    method, query, args = pool.calls[0]
    assert method == "execute"
    assert "ON CONFLICT (tenant_id, workspace_id, user_id)" in query
    assert args == ("ci-1", "acme", "ws-1", "bob", "Be terse.", "bob", NOW)


async def test_instructions_clear_deletes_by_scope():
    pool = FakePool()
    repo = PostgresCustomInstructionsRepository(pool)

    await repo.clear(TenantId("acme"), WorkspaceId("ws-1"), None)

    method, query, args = pool.calls[0]
    assert method == "execute"
    assert query.strip().startswith("DELETE FROM agent_custom_instructions")
    assert args == ("acme", "ws-1", None)


# --- PostgresAgentMemoryRepository --------------------------------------------


async def test_memory_add_passes_all_fields():
    pool = FakePool()
    repo = PostgresAgentMemoryRepository(pool)

    await repo.add(memory())

    method, query, args = pool.calls[0]
    assert method == "execute"
    assert "INSERT INTO agent_memories" in query
    assert args == ("mem-1", "acme", "ws-1", "Prefers dark mode", "alice", NOW, NOW)


async def test_memory_list_for_workspace_maps_rows():
    pool = FakePool(rows=[memory_row("mem-1"), memory_row("mem-2", text="Uses uv")])
    repo = PostgresAgentMemoryRepository(pool)

    memories = await repo.list_for_workspace(TenantId("acme"), WorkspaceId("ws-1"))

    assert memories == [memory("mem-1"), memory("mem-2", text="Uses uv")]
    method, query, args = pool.calls[0]
    assert method == "fetch"
    assert "ORDER BY created_at DESC" in query
    assert args == ("acme", "ws-1")


async def test_memory_recent_passes_limit():
    pool = FakePool(rows=[memory_row()])
    repo = PostgresAgentMemoryRepository(pool)

    memories = await repo.recent(TenantId("acme"), WorkspaceId("ws-1"), limit=5)

    assert memories == [memory()]
    assert pool.calls[0][2] == ("acme", "ws-1", 5)


async def test_memory_recent_clamps_negative_limit_to_zero():
    pool = FakePool(rows=[])
    repo = PostgresAgentMemoryRepository(pool)

    assert await repo.recent(TenantId("acme"), WorkspaceId("ws-1"), limit=-3) == []
    assert pool.calls[0][2] == ("acme", "ws-1", 0)


async def test_memory_relevant_builds_one_ilike_per_token():
    pool = FakePool(rows=[memory_row()])
    repo = PostgresAgentMemoryRepository(pool)

    memories = await repo.relevant(
        TenantId("acme"), WorkspaceId("ws-1"), "Dark MODE dark!", limit=10
    )

    assert memories == [memory()]
    method, query, args = pool.calls[0]
    assert method == "fetch"
    assert "text ILIKE $4 OR text ILIKE $5" in query
    assert "$6" not in query  # "dark" deduped: exactly two tokens
    assert args == ("acme", "ws-1", 10, "%dark%", "%mode%")


async def test_memory_relevant_clamps_negative_limit_to_zero():
    pool = FakePool(rows=[])
    repo = PostgresAgentMemoryRepository(pool)

    await repo.relevant(TenantId("acme"), WorkspaceId("ws-1"), "roadmap", limit=-1)

    assert pool.calls[0][2] == ("acme", "ws-1", 0, "%roadmap%")


async def test_memory_relevant_without_usable_tokens_skips_the_query():
    pool = FakePool(rows=[memory_row()])
    repo = PostgresAgentMemoryRepository(pool)

    assert await repo.relevant(TenantId("acme"), WorkspaceId("ws-1"), "a b !", 10) == []
    assert await repo.relevant(TenantId("acme"), WorkspaceId("ws-1"), "", 10) == []
    assert pool.calls == []


async def test_memory_get_maps_row():
    pool = FakePool(row=memory_row())
    repo = PostgresAgentMemoryRepository(pool)

    found = await repo.get(TenantId("acme"), AgentMemoryId("mem-1"))

    assert found == memory()
    assert pool.calls[0][2] == ("acme", "mem-1")


async def test_memory_get_returns_none_when_missing():
    pool = FakePool(row=None)
    repo = PostgresAgentMemoryRepository(pool)

    assert await repo.get(TenantId("acme"), AgentMemoryId("mem-404")) is None


async def test_memory_update_sets_text_and_updated_at():
    pool = FakePool()
    repo = PostgresAgentMemoryRepository(pool)
    later = datetime(2026, 2, 1, tzinfo=UTC)
    updated = AgentMemory(
        id=AgentMemoryId("mem-1"),
        tenant_id=TenantId("acme"),
        workspace_id=WorkspaceId("ws-1"),
        text="Prefers light mode now",
        created_by=UserId("alice"),
        created_at=NOW,
        updated_at=later,
    )

    await repo.update(updated)

    method, query, args = pool.calls[0]
    assert method == "execute"
    assert "UPDATE agent_memories" in query
    assert args == ("acme", "mem-1", "Prefers light mode now", later)


async def test_memory_delete_scopes_by_tenant():
    pool = FakePool()
    repo = PostgresAgentMemoryRepository(pool)

    await repo.delete(TenantId("acme"), AgentMemoryId("mem-1"))

    method, query, args = pool.calls[0]
    assert method == "execute"
    assert query.startswith("DELETE FROM agent_memories")
    assert args == ("acme", "mem-1")
