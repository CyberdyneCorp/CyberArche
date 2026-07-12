-- 0010_notifications: a per-user inbox. A row is created when a user is
-- @mentioned in a comment (and, in future, other events). Read-tracked per user.

BEGIN;

CREATE TABLE notifications (
    id           TEXT PRIMARY KEY,
    tenant_id    TEXT NOT NULL,
    recipient_id TEXT NOT NULL,
    kind         TEXT NOT NULL,            -- 'mention' (more kinds later)
    actor_id     TEXT NOT NULL,
    document_id  TEXT REFERENCES documents (id) ON DELETE CASCADE,
    comment_id   TEXT,
    snippet      TEXT NOT NULL DEFAULT '',
    read         BOOLEAN NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ NOT NULL
);
CREATE INDEX notifications_recipient_idx
    ON notifications (tenant_id, recipient_id, created_at DESC);

ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;
CREATE POLICY notifications_tenant_isolation ON notifications
    USING (tenant_id = current_setting('cyberarche.tenant_id', TRUE));

COMMIT;
