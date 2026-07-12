-- 0013_agent_skills: named, reusable agent instructions ("skills") per workspace.
-- A skill stores an instruction template with optional {variable} placeholders;
-- invoking it expands the variables into an instruction run through the agent.
-- Tenant-isolated via RLS, mirroring the templates table.

BEGIN;

CREATE TABLE agent_skills (
    id           TEXT PRIMARY KEY,
    tenant_id    TEXT NOT NULL,
    workspace_id TEXT NOT NULL REFERENCES workspaces (id) ON DELETE CASCADE,
    name         TEXT NOT NULL,
    description  TEXT NOT NULL DEFAULT '',
    instruction  TEXT NOT NULL,
    variables    JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_by   TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL
);
CREATE INDEX agent_skills_workspace_idx ON agent_skills (tenant_id, workspace_id);

ALTER TABLE agent_skills ENABLE ROW LEVEL SECURITY;
CREATE POLICY agent_skills_tenant_isolation ON agent_skills
    USING (tenant_id = current_setting('cyberarche.tenant_id', TRUE));

COMMIT;
