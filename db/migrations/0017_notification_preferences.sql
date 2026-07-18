-- 0017_notification_preferences: per-user notification settings. In-app is
-- always on (not stored); these toggles gate additional delivery channels
-- (email/push) and per-kind delivery (mentions, agent task results). Defaults
-- preserve today's behaviour: in-app + mentions on, email/push off.

BEGIN;

CREATE TABLE notification_preferences (
    tenant_id             TEXT NOT NULL,
    user_id               TEXT NOT NULL,
    email_enabled         BOOLEAN NOT NULL DEFAULT FALSE,
    push_enabled          BOOLEAN NOT NULL DEFAULT FALSE,
    mentions_enabled      BOOLEAN NOT NULL DEFAULT TRUE,
    agent_results_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (tenant_id, user_id)
);

ALTER TABLE notification_preferences ENABLE ROW LEVEL SECURITY;
CREATE POLICY notification_preferences_tenant_isolation ON notification_preferences
    USING (tenant_id = current_setting('cyberarche.tenant_id', TRUE));

COMMIT;
