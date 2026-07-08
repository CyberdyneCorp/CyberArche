-- 0003_connector_slugs: connectors are workspace-scoped and namespaced by slug

BEGIN;

ALTER TABLE mcp_connectors
    ADD COLUMN slug TEXT NOT NULL DEFAULT '',
    ALTER COLUMN workspace_id SET NOT NULL;

CREATE UNIQUE INDEX mcp_connectors_slug_idx
    ON mcp_connectors (tenant_id, workspace_id, slug);

COMMIT;
