-- 0001_initial: core schema for bootstrap-cyberarche
-- Tenant isolation: every tenant-owned table carries tenant_id and an RLS
-- policy keyed to the app.tenant_id session setting (defense-in-depth behind
-- the explicit tenant scoping in every repository query).

BEGIN;

CREATE TABLE workspaces (
    id                TEXT PRIMARY KEY,
    tenant_id         TEXT NOT NULL,
    name              TEXT NOT NULL,
    created_by        TEXT NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL,
    rag_project_slug  TEXT
);
CREATE INDEX workspaces_tenant_idx ON workspaces (tenant_id);

CREATE TABLE documents (
    id                       TEXT PRIMARY KEY,
    workspace_id             TEXT NOT NULL REFERENCES workspaces (id) ON DELETE CASCADE,
    tenant_id                TEXT NOT NULL,
    title                    TEXT NOT NULL,
    parent_id                TEXT REFERENCES documents (id) ON DELETE CASCADE,
    position                 INTEGER NOT NULL DEFAULT 0,
    created_by               TEXT NOT NULL,
    created_at               TIMESTAMPTZ NOT NULL,
    updated_at               TIMESTAMPTZ NOT NULL,
    trashed                  BOOLEAN NOT NULL DEFAULT FALSE,
    trashed_from_parent_id   TEXT
);
CREATE INDEX documents_tenant_idx ON documents (tenant_id);
CREATE INDEX documents_siblings_idx ON documents (workspace_id, parent_id, position)
    WHERE trashed = FALSE;
CREATE INDEX documents_trash_idx ON documents (workspace_id) WHERE trashed = TRUE;

CREATE TABLE snapshots (
    id             TEXT PRIMARY KEY,
    document_id    TEXT NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    seq            INTEGER NOT NULL,
    content        JSONB NOT NULL,
    state_vector   BYTEA NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL,
    restored_from  TEXT,
    created_by     TEXT,
    UNIQUE (document_id, seq)
);

-- CRDT update log (realtime-collaboration spec): the document is
-- reconstructable from snapshots + updates after any restart.
CREATE TABLE crdt_updates (
    id           BIGSERIAL PRIMARY KEY,
    document_id  TEXT NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    update       BYTEA NOT NULL,
    origin       TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX crdt_updates_document_idx ON crdt_updates (document_id, id);

CREATE TABLE workspace_memberships (
    workspace_id  TEXT NOT NULL REFERENCES workspaces (id) ON DELETE CASCADE,
    user_id       TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('owner', 'editor', 'commenter', 'viewer')),
    granted_at    TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (workspace_id, user_id)
);

CREATE TABLE document_grants (
    document_id  TEXT NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    user_id      TEXT NOT NULL,
    role         TEXT NOT NULL CHECK (role IN ('owner', 'editor', 'commenter', 'viewer')),
    granted_at   TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (document_id, user_id)
);

CREATE TABLE share_links (
    id           TEXT PRIMARY KEY,
    document_id  TEXT NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    permission   TEXT NOT NULL CHECK (permission IN ('view', 'comment', 'edit')),
    created_by   TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL,
    expires_at   TIMESTAMPTZ,
    revoked_at   TIMESTAMPTZ
);

CREATE TABLE agent_runs (
    id           TEXT PRIMARY KEY,
    tenant_id    TEXT NOT NULL,
    document_id  TEXT REFERENCES documents (id) ON DELETE SET NULL,
    user_id      TEXT NOT NULL,
    model        TEXT NOT NULL,
    prompt       TEXT NOT NULL,
    tools_used   JSONB NOT NULL DEFAULT '[]',
    outcome      TEXT,
    started_at   TIMESTAMPTZ NOT NULL,
    finished_at  TIMESTAMPTZ
);
CREATE INDEX agent_runs_document_idx ON agent_runs (document_id, started_at DESC);

CREATE TABLE mcp_connectors (
    id                     TEXT PRIMARY KEY,
    tenant_id              TEXT NOT NULL,
    workspace_id           TEXT REFERENCES workspaces (id) ON DELETE CASCADE,
    name                   TEXT NOT NULL,
    endpoint               TEXT NOT NULL,
    credentials_encrypted  BYTEA,
    enabled                BOOLEAN NOT NULL DEFAULT TRUE,
    created_by             TEXT NOT NULL,
    created_at             TIMESTAMPTZ NOT NULL
);
CREATE INDEX mcp_connectors_tenant_idx ON mcp_connectors (tenant_id);

-- Row-Level Security -------------------------------------------------------
-- The application role runs with SET app.tenant_id = '<tenant>'.

ALTER TABLE workspaces     ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents      ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_runs     ENABLE ROW LEVEL SECURITY;
ALTER TABLE mcp_connectors ENABLE ROW LEVEL SECURITY;

CREATE POLICY workspaces_tenant_isolation ON workspaces
    USING (tenant_id = current_setting('app.tenant_id', true));
CREATE POLICY documents_tenant_isolation ON documents
    USING (tenant_id = current_setting('app.tenant_id', true));
CREATE POLICY agent_runs_tenant_isolation ON agent_runs
    USING (tenant_id = current_setting('app.tenant_id', true));
CREATE POLICY mcp_connectors_tenant_isolation ON mcp_connectors
    USING (tenant_id = current_setting('app.tenant_id', true));

COMMIT;
