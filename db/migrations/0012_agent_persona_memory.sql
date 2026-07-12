-- 0012_agent_persona_memory: give the agent a stored persona and durable memory.
--
-- agent_custom_instructions: per-workspace "house style" for the agent, plus an
-- optional per-user personal layer (user_id NULL = the shared workspace layer).
-- Unique on (tenant_id, workspace_id, user_id) so a set replaces in place.
--
-- agent_memories: durable notes scoped to a workspace, injected into later runs
-- (recency + keyword selection). Both tables are tenant-isolated via RLS,
-- mirroring the templates table.

BEGIN;

CREATE TABLE agent_custom_instructions (
    id           TEXT PRIMARY KEY,
    tenant_id    TEXT NOT NULL,
    workspace_id TEXT NOT NULL REFERENCES workspaces (id) ON DELETE CASCADE,
    user_id      TEXT,   -- NULL = shared workspace layer; else a personal layer
    instructions TEXT NOT NULL,
    updated_by   TEXT NOT NULL,
    updated_at   TIMESTAMPTZ NOT NULL,
    UNIQUE (tenant_id, workspace_id, user_id)
);

ALTER TABLE agent_custom_instructions ENABLE ROW LEVEL SECURITY;
CREATE POLICY agent_custom_instructions_tenant_isolation
    ON agent_custom_instructions
    USING (tenant_id = current_setting('cyberarche.tenant_id', TRUE));

CREATE TABLE agent_memories (
    id           TEXT PRIMARY KEY,
    tenant_id    TEXT NOT NULL,
    workspace_id TEXT NOT NULL REFERENCES workspaces (id) ON DELETE CASCADE,
    text         TEXT NOT NULL,
    created_by   TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL,
    updated_at   TIMESTAMPTZ NOT NULL
);
CREATE INDEX agent_memories_recent_idx
    ON agent_memories (tenant_id, workspace_id, created_at DESC);

ALTER TABLE agent_memories ENABLE ROW LEVEL SECURITY;
CREATE POLICY agent_memories_tenant_isolation ON agent_memories
    USING (tenant_id = current_setting('cyberarche.tenant_id', TRUE));

COMMIT;
