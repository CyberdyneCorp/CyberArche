-- 0014_scheduled_agents: autonomous agent tasks that run on a schedule with no
-- live user. A task is authorized by its stored owner (never the service
-- identity); the scheduler claims a due task with a lease so it runs at most
-- once per tick. agent_task_runs audits every execution.

BEGIN;

CREATE TABLE scheduled_agent_tasks (
    id               TEXT PRIMARY KEY,
    tenant_id        TEXT NOT NULL,
    owner_id         TEXT NOT NULL,
    name             TEXT NOT NULL,
    instruction      TEXT NOT NULL,
    workspace_id     TEXT NOT NULL REFERENCES workspaces (id) ON DELETE CASCADE,
    document_id      TEXT REFERENCES documents (id) ON DELETE SET NULL,
    schedule_cron    TEXT NOT NULL,
    enabled          BOOLEAN NOT NULL DEFAULT TRUE,
    next_run_at      TIMESTAMPTZ,
    running          BOOLEAN NOT NULL DEFAULT FALSE,
    lease_until      TIMESTAMPTZ,
    max_tool_rounds  INT NOT NULL DEFAULT 8,
    max_wall_seconds INT NOT NULL DEFAULT 120,
    max_actions      INT NOT NULL DEFAULT 20,
    created_at       TIMESTAMPTZ NOT NULL,
    updated_at       TIMESTAMPTZ NOT NULL
);
CREATE INDEX scheduled_agent_tasks_due_idx
    ON scheduled_agent_tasks (enabled, next_run_at);
CREATE INDEX scheduled_agent_tasks_workspace_idx
    ON scheduled_agent_tasks (tenant_id, workspace_id);

ALTER TABLE scheduled_agent_tasks ENABLE ROW LEVEL SECURITY;
CREATE POLICY scheduled_agent_tasks_tenant_isolation ON scheduled_agent_tasks
    USING (tenant_id = current_setting('cyberarche.tenant_id', TRUE));

CREATE TABLE agent_task_runs (
    id           TEXT PRIMARY KEY,
    tenant_id    TEXT NOT NULL,
    task_id      TEXT NOT NULL REFERENCES scheduled_agent_tasks (id) ON DELETE CASCADE,
    owner_id     TEXT NOT NULL,
    trigger      TEXT NOT NULL,
    document_id  TEXT,
    outcome      TEXT NOT NULL,
    detail       TEXT NOT NULL DEFAULT '',
    tools_used   JSONB NOT NULL DEFAULT '[]'::jsonb,
    started_at   TIMESTAMPTZ NOT NULL,
    finished_at  TIMESTAMPTZ
);
CREATE INDEX agent_task_runs_task_idx
    ON agent_task_runs (tenant_id, task_id, started_at DESC);

ALTER TABLE agent_task_runs ENABLE ROW LEVEL SECURITY;
CREATE POLICY agent_task_runs_tenant_isolation ON agent_task_runs
    USING (tenant_id = current_setting('cyberarche.tenant_id', TRUE));

COMMIT;
