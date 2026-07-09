-- 0008_folders: dedicated folders that group documents within a workspace,
-- inside a teamspace (shared) or the private space (creator-only).

BEGIN;

CREATE TABLE folders (
    id                TEXT PRIMARY KEY,
    workspace_id      TEXT NOT NULL REFERENCES workspaces (id) ON DELETE CASCADE,
    tenant_id         TEXT NOT NULL,
    name              TEXT NOT NULL,
    created_by        TEXT NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL,
    -- NULL => private folder (creator-only); otherwise the owning teamspace.
    teamspace_id      TEXT REFERENCES teamspaces (id) ON DELETE CASCADE,
    -- Nested folders cascade with their parent.
    parent_folder_id  TEXT REFERENCES folders (id) ON DELETE CASCADE
);
CREATE INDEX folders_workspace_idx ON folders (tenant_id, workspace_id);
CREATE INDEX folders_teamspace_idx ON folders (teamspace_id);
CREATE INDEX folders_parent_idx ON folders (parent_folder_id);

-- Deleting a folder must never destroy documents: they detach (SET NULL) and
-- fall back to the folder's teamspace or the private space (design D-4).
ALTER TABLE documents
    ADD COLUMN folder_id TEXT REFERENCES folders (id) ON DELETE SET NULL;
CREATE INDEX documents_folder_idx ON documents (folder_id)
    WHERE trashed = FALSE;

ALTER TABLE folders ENABLE ROW LEVEL SECURITY;
CREATE POLICY folders_tenant_isolation ON folders
    USING (tenant_id = current_setting('cyberarche.tenant_id', TRUE));

COMMIT;
