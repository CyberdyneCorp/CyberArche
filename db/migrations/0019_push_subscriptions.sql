-- 0019_push_subscriptions: per-user browser Web Push subscriptions (VAPID /
-- RFC 8291). The browser mints one row per device when the user enables push;
-- `endpoint` (the push service URL) is the natural unique key across all users,
-- so it is the primary key. p256dh + auth are the subscription's encryption
-- keys. Tenant-isolated like notification_preferences (RLS on tenant_id).

BEGIN;

CREATE TABLE push_subscriptions (
    tenant_id  TEXT NOT NULL,
    user_id    TEXT NOT NULL,
    endpoint   TEXT PRIMARY KEY,
    p256dh     TEXT NOT NULL,
    auth       TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX push_subscriptions_tenant_user
    ON push_subscriptions (tenant_id, user_id);

ALTER TABLE push_subscriptions ENABLE ROW LEVEL SECURITY;
CREATE POLICY push_subscriptions_tenant_isolation ON push_subscriptions
    USING (tenant_id = current_setting('cyberarche.tenant_id', TRUE));

COMMIT;
