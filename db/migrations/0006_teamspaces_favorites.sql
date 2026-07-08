-- 0006_teamspaces_favorites: team-owned document groupings + per-user favourites

BEGIN;

CREATE TABLE teamspaces (
    id            TEXT PRIMARY KEY,
    workspace_id  TEXT NOT NULL REFERENCES workspaces (id) ON DELETE CASCADE,
    tenant_id     TEXT NOT NULL,
    name          TEXT NOT NULL,
    icon          TEXT NOT NULL DEFAULT 'T',
    created_by    TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL
);
CREATE INDEX teamspaces_workspace_idx ON teamspaces (tenant_id, workspace_id);

CREATE TABLE teamspace_memberships (
    teamspace_id  TEXT NOT NULL REFERENCES teamspaces (id) ON DELETE CASCADE,
    user_id       TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('owner', 'editor', 'commenter', 'viewer')),
    granted_at    TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (teamspace_id, user_id)
);
CREATE INDEX teamspace_memberships_user_idx ON teamspace_memberships (user_id);

-- Deleting a teamspace must never destroy documents: they fall back to
-- workspace level (design D-5).
ALTER TABLE documents
    ADD COLUMN teamspace_id TEXT REFERENCES teamspaces (id) ON DELETE SET NULL;
CREATE INDEX documents_teamspace_idx ON documents (teamspace_id)
    WHERE trashed = FALSE;

CREATE TABLE favorites (
    user_id      TEXT NOT NULL,
    document_id  TEXT NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, document_id)
);

ALTER TABLE teamspaces ENABLE ROW LEVEL SECURITY;
CREATE POLICY teamspaces_tenant_isolation ON teamspaces
    USING (tenant_id = current_setting('app.tenant_id', true));

COMMIT;
