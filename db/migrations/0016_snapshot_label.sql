-- Version history (version-history spec): a snapshot MAY carry a human-friendly
-- name so versions can be labelled and renamed.
ALTER TABLE snapshots ADD COLUMN label text;
