-- 0020_collections: Notion-style collections (databases). A collection is a
-- named property schema plus one or more named views; its rows ARE documents
-- (collection_id + typed property values) so they open as full pages. The
-- schema and views are stored as JSONB; later PRs add board/gallery/calendar
-- views over the same rows.

BEGIN;

CREATE TABLE collections (
    id            TEXT PRIMARY KEY,
    tenant_id     TEXT NOT NULL,
    workspace_id  TEXT NOT NULL REFERENCES workspaces (id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    properties    JSONB NOT NULL DEFAULT '[]',
    views         JSONB NOT NULL DEFAULT '[]',
    created_at    TIMESTAMPTZ NOT NULL
);
CREATE INDEX collections_workspace_idx ON collections (tenant_id, workspace_id);

ALTER TABLE collections ENABLE ROW LEVEL SECURITY;
CREATE POLICY collections_tenant_isolation ON collections
    USING (tenant_id = current_setting('cyberarche.tenant_id', TRUE));

-- Rows of a collection are documents. Deleting a collection detaches its rows
-- (SET NULL) so the documents survive as ordinary pages.
ALTER TABLE documents
    ADD COLUMN collection_id TEXT REFERENCES collections (id) ON DELETE SET NULL,
    ADD COLUMN properties JSONB NOT NULL DEFAULT '{}';
CREATE INDEX documents_collection_idx ON documents (collection_id)
    WHERE trashed = FALSE;

COMMIT;
