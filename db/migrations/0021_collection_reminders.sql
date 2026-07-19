-- 0021_collection_reminders: de-dup store for date-property reminders. A row's
-- date property can carry a reminder lead time; a scheduled sweep notifies the
-- row's creator once when the date (minus the lead) is reached. One row per
-- (document_id, property_id) holds the last date value a reminder fired for, so
-- a reminder fires at most once per value and re-arms when the date changes.
--
-- No tenant_id/RLS: keyed by document_id (globally unique) and only ever
-- touched by the background sweep, which runs as the table owner (bypassing
-- RLS) exactly like the notification digest's cross-tenant enumeration.

BEGIN;

CREATE TABLE collection_reminders (
    document_id    TEXT NOT NULL,
    property_id    TEXT NOT NULL,
    reminded_value TEXT NOT NULL,
    PRIMARY KEY (document_id, property_id)
);

COMMIT;
