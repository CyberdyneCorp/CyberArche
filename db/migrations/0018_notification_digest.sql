-- 0018_notification_digest: the scheduled email digest of unread notifications.
-- Capture the user's email (from their verified token claims when they save
-- preferences) so the digest can reach them, and record when a digest last ran
-- for cadence + de-duplication. Both default NULL: no email captured yet, and
-- no digest has run.

BEGIN;

ALTER TABLE notification_preferences ADD COLUMN email text;
ALTER TABLE notification_preferences ADD COLUMN last_digest_at timestamptz;

COMMIT;
