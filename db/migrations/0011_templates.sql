-- 0011_templates: named page templates per workspace. Each captures a document's
-- block content at save time; creating a document from a template copies its
-- blocks (with fresh ids) into a new document.

BEGIN;

CREATE TABLE templates (
    id           TEXT PRIMARY KEY,
    tenant_id    TEXT NOT NULL,
    workspace_id TEXT NOT NULL REFERENCES workspaces (id) ON DELETE CASCADE,
    name         TEXT NOT NULL,
    created_by   TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL,
    content      JSONB NOT NULL   -- the captured block tree
);
CREATE INDEX templates_workspace_idx ON templates (tenant_id, workspace_id);

ALTER TABLE templates ENABLE ROW LEVEL SECURITY;
CREATE POLICY templates_tenant_isolation ON templates
    USING (tenant_id = current_setting('cyberarche.tenant_id', TRUE));

COMMIT;
