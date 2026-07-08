# Design

## D-1: Restore is a CRDT update, not a content overwrite

The tempting fix is to write `snapshot.content` straight into the document row.
It would be wrong. The document body's source of truth is the CRDT update log
(`document-model`: "canonical block content SHALL be stored as a CRDT
document"); any writer that bypasses it diverges from every connected editor,
which holds its own Yjs replica and would never see the change — and would
happily overwrite it on the next keystroke.

So restore goes through the same seam the AI agent uses:

```
state  = realtime.current_state(caller, document_id)
update = engine.replace_blocks(state, snapshot.content["blocks"])
realtime.apply(caller, document_id, update, origin=f"restore:{caller.user_id}")
```

`RealtimeUseCases.apply` already appends to the update log, publishes on the
peer bus for cross-replica fanout, and triggers compaction. Restore inherits
all of it for free, and open browsers converge live.

Consequence: a restore is an ordinary, undoable edit. It does not rewind
history; it moves the document forward to a prior content. That is the correct
semantics for a CRDT and matches the spec's "record a new snapshot".

## D-2: `replace_blocks` diffs; it does not clear-and-append

Clearing the array and re-appending every block would work for a single writer
and behave badly under concurrency: a peer inserting a block during the restore
would have its insert dropped or duplicated, and every block id would churn,
invalidating comment anchors (comments are keyed by `block_id`).

`replace_blocks` therefore reconciles by block id:

- blocks present in the snapshot but not in the document → insert at position
- blocks present in both → merge the snapshot's `data` into the existing map
  (same merge semantics as `update_block`, so a whiteboard scene attached to
  the block survives)
- blocks present in the document but not in the snapshot → delete
- order is fixed up to match the snapshot

All inside one transaction, so it lands as one update and one undo step.

Blocks whose `type` changed between the snapshot and now are replaced wholesale
rather than merged, since merging data across types is meaningless.

## D-3: Authorization is unchanged and re-checked

`restore` already requires `editor`. `realtime.apply` independently requires
`editor` too. That double check is deliberate and cheap: it means no future
caller of `apply` can smuggle in a write, which is the property
`permissions-sharing` ("enforced uniformly across all surfaces") depends on.

## D-4: Where the snapshot's blocks come from

`Snapshot.content` is the materialized JSON `{"blocks": [...]}`. A snapshot
also carries a `state_vector`, which is tempting to use with `engine.diff`.
It cannot serve here: the state vector describes what the snapshot's author
*had seen*, not the content, and diffing against it would replay intervening
edits rather than undo them. Restore is defined over `content`.

We keep writing `state_vector` on the new snapshot row for forensics.

## D-5: Idempotence

Restoring the same snapshot twice produces an empty second update (nothing to
insert, merge, or delete). `apply` on an empty update is a no-op append; we
skip the apply entirely when `replace_blocks` returns an update with no
changes, so history is not polluted with empty entries. The snapshot row is
still recorded, because "I restored this" is a fact worth keeping.
