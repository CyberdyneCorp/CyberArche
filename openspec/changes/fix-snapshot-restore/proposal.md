# Fix snapshot restore

## Why

`POST /api/v1/documents/{id}/snapshots/{sid}/restore` returns `200` and does
nothing to the document. `SnapshotUseCases.restore` reads the source snapshot
and calls `record(...)`, which only appends a new snapshot row. It cannot
restore: the class holds no `UpdateLogPort` and no `CrdtEnginePort`, so it has
no way to write the document body.

Both existing tests pass against this no-op:

- `tests/test_snapshots.py` asserts `restored.content == {...}` — that is the
  *new snapshot row's* content, copied by `record()`, not the document's.
- `tests/test_http_api.py` asserts `restored["restored_from"] == snapshot["id"]`.

Neither reads the document back. The spec's scenario says the system SHALL
"replace the current content with the snapshot content"; only its second half
("record a new snapshot") was ever implemented, and only that half was tested.

This is a silent data-integrity failure: a user restores a version, the API
reports success, and their content is unchanged. No frontend caller exists
today, so it is not yet user-visible — but the endpoint is live and the MCP
surface reaches the same use case.

## What Changes

- Add `replace_blocks` to `CrdtEnginePort` and the pycrdt adapter: an
  incremental update that makes the document body equal a given block list.
- `SnapshotUseCases.restore` composes over `RealtimeUseCases`, exactly as the
  agent's `apply_blocks` does: read current state, compute the replacing
  update, apply it. Restores therefore persist to the update log, broadcast to
  every open editor over the peer bus, and are attributed (`origin`).
- Restore keeps recording a new snapshot, so history stays append-only and the
  restore itself is undoable by restoring the snapshot it superseded.
- Restore requires `editor` (unchanged) and remains enforced on every surface.

## Non-goals

- Trash purge (`restorable until permanently purged`) — a separate gap, tracked
  separately; it needs a retention policy decision.
- A frontend version-history UI. This change makes the endpoint honest; the UI
  can follow.
- Restoring a snapshot into a *different* document.

## Impact

- `document-model` capability: the "Version snapshots" requirement gains
  scenarios that pin the half nobody tested.
- `realtime-collaboration`: restores are ordinary CRDT updates, so open editors
  converge rather than silently diverging from the server.
- Ports change (`CrdtEnginePort`), so the port-contract suite grows a case.
