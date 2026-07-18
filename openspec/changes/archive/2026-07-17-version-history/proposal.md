# Version history: named versions + block-level diff

## Why

The system already persists immutable document snapshots and can list/restore
them (`document-model`), but there's no way to **name** a version or **see what
changed** between two points — you can only blind-restore. This adds named
versions and a block-level diff, and a history timeline UI.

## What Changes

- Snapshots gain an optional **label** (migration 0016 adds `snapshots.label`).
  Recording a snapshot MAY set a label; a version MAY be renamed.
- New **diff** capability: `SnapshotUseCases.diff(caller, document_id, from_id,
  to_id?)` compares two snapshots' blocks (or a snapshot vs the current state
  when `to_id` is omitted) and returns per-block changes (added / removed /
  modified, with text). Pure `diff_blocks(old, new)` in the domain.
- New endpoints: `GET /documents/{id}/snapshots/diff?from=&to=`, and label on
  the record endpoint + `PATCH /documents/{id}/snapshots/{sid}` to rename.
- Frontend: a **History** modal (timeline of versions with time / author /
  label, view + restore, and a compare view rendering the block diff).

## Impact

- Affected specs: `document-model`.
- Affected code: `domain/snapshots.py` (label + `diff_blocks`),
  `use_cases/snapshots.py`, snapshot routes in `routers/documents.py`,
  Postgres snapshot repo + `db/migrations/0016_snapshot_label.sql`,
  in-memory fake; a `HistoryModal` component + viewmodel + api client.
