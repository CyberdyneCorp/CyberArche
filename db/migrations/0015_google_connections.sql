-- 0015_google_connections: a personal Google Workspace connection per user per
-- workspace. Access + refresh tokens are stored ENCRYPTED (envelope encryption
-- via the connector SecretBox); only metadata is ever read back. Tenant-isolated
-- via RLS. Google is the only first-party SaaS connector; others use external-MCP.

BEGIN;

CREATE TABLE google_connections (
    id                      TEXT PRIMARY KEY,
    tenant_id               TEXT NOT NULL,
    workspace_id            TEXT NOT NULL REFERENCES workspaces (id) ON DELETE CASCADE,
    user_id                 TEXT NOT NULL,
    google_email            TEXT NOT NULL DEFAULT '',
    access_token_encrypted  BYTEA NOT NULL,
    refresh_token_encrypted BYTEA NOT NULL,
    token_expires_at        TIMESTAMPTZ,
    scopes                  JSONB NOT NULL DEFAULT '[]'::jsonb,
    status                  TEXT NOT NULL DEFAULT 'connected',
    created_at              TIMESTAMPTZ NOT NULL,
    updated_at              TIMESTAMPTZ NOT NULL,
    UNIQUE (tenant_id, workspace_id, user_id)
);

ALTER TABLE google_connections ENABLE ROW LEVEL SECURITY;
CREATE POLICY google_connections_tenant_isolation ON google_connections
    USING (tenant_id = current_setting('cyberarche.tenant_id', TRUE));

COMMIT;
