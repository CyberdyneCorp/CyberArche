-- 0005_api_keys: personal API keys for external MCP clients

BEGIN;

CREATE TABLE api_keys (
    id            TEXT PRIMARY KEY,
    tenant_id     TEXT NOT NULL,
    user_id       TEXT NOT NULL,
    name          TEXT NOT NULL,
    secret_hash   TEXT NOT NULL UNIQUE,
    prefix        TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL,
    expires_at    TIMESTAMPTZ,
    revoked_at    TIMESTAMPTZ,
    last_used_at  TIMESTAMPTZ
);
CREATE INDEX api_keys_user_idx ON api_keys (tenant_id, user_id);

ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;
CREATE POLICY api_keys_tenant_isolation ON api_keys
    USING (tenant_id = current_setting('app.tenant_id', true));

COMMIT;
