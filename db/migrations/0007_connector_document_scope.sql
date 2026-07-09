BEGIN;

-- A connector may be scoped to a single document (NULL = workspace-wide).
-- Scoped connectors are removed when their document is purged.
ALTER TABLE mcp_connectors
    ADD COLUMN document_id TEXT REFERENCES documents (id) ON DELETE CASCADE;

COMMIT;
