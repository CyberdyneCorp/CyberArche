# Permanently delete a trashed document

## Why

`document-model` says trashed documents are "restorable **until permanently
purged**." Nothing purges. `DocumentUseCases` has `trash`, `restore`, and
`list_trashed` but no permanent delete; there is no purge job, retention, or
endpoint anywhere. Trashed documents are retained forever, and the "until"
bound the spec promises is unenforceable — a normative clause with no scenario,
no test, and no implementation.

## What Changes

- A user can permanently delete a document that is in the trash. The document
  and its entire subtree are removed, along with everything they own — CRDT
  updates, snapshots, comments, share links, grants, and favourites.
- Purge is only reachable from the trash: a live document must be trashed
  first, so the trash keeps its role as the recoverable safety net.
- `DELETE /api/v1/documents/{id}/trash` performs the purge; the existing
  `DELETE /api/v1/documents/{id}` continues to trash (soft delete).

## Non-goals

- Automatic retention / TTL purging. That needs a policy decision (how long)
  and a scheduled worker; this change gives the user an explicit, immediate
  purge. Auto-retention can build on the same use case later.
- Purging a whole workspace or teamspace.
- A trash "empty all" bulk action (can follow, one purge per document).

## Impact

- `document-model`: the "Soft delete and trash" requirement gains the purge
  half that was only ever prose.
- Ports: `DocumentRepository` gains `purge`. The port-contract suite covers it
  against real Postgres, where the FK cascade actually runs.
- Postgres already cascades every table referencing `documents` (and children
  via `parent_id`), so the adapter is one `DELETE`; the in-memory adapter
  removes the subtree explicitly.
