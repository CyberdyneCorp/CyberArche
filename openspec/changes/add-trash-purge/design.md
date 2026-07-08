# Design

## D-1: Purge only from the trash

The trash exists so a delete is recoverable. If purge could hit a live
document, the safety net would be one mis-click from useless. So `purge`
requires the document to be already trashed; a live document must be trashed
first. This also gives a natural two-step confirmation without a modal
contract: delete (trash) → delete permanently (purge).

`restore` already rejects a non-trashed document with `ValidationFailed`; purge
uses the same guard, inverted.

## D-2: Cascade is a repository concern

A document owns rows in six other tables (crdt_updates, snapshots, comments,
share_links, document_grants, favorites) and can have child documents. In
Postgres every one of these already declares `ON DELETE CASCADE` (children via
`parent_id ON DELETE CASCADE`), so purge is a single
`DELETE FROM documents WHERE id = $1` and the database removes the rest
atomically. `agent_runs.document_id` is `ON DELETE SET NULL` — deliberately —
so the audit trail survives the document.

The port method therefore owns the cascade: `DocumentRepository.purge` removes
the document and its descendants and returns the purged ids. The use case does
not orchestrate per-table deletes; that would duplicate the schema's cascade in
application code and drift from it.

The in-memory adapter has no database cascade, so it walks the subtree and
removes each document from its store. It does *not* reach across store
boundaries, so it leaves the sibling stores' rows behind — a divergence from
Postgres that is real at the port boundary (`favorites.list_for_user` returns
raw ids and would show a stale favourite) but invisible at the use-case
boundary: `FavoriteUseCases.list` drops favourites whose document no longer
resolves, and snapshots/comments/updates are only reachable through the now-gone
document. The port contract therefore promises only what both adapters deliver —
the document and subtree are removed and the ids returned; the owned-row cascade
is a Postgres storage guarantee, asserted against the real schema.

## D-3: Subtree, not just the row

Purging a document with children must not leave orphans pointing at a deleted
parent. Postgres cascades `parent_id`; the in-memory adapter recurses. Purge is
defined over the subtree so both adapters agree: after purging a root, none of
its descendants remain or are restorable.

The returned id list is the whole subtree, so a caller (and the contract test)
can assert exactly what was removed.

## D-4: Authorization

Purge requires `editor` on the document, matching `trash` and `restore`. An
editor who could trash and restore a document can also purge it; there is no
separate destructive tier today, and gating purge behind `owner` would stop an
editor from cleaning up a document they themselves trashed. The check runs
before any deletion, on the same seam as every other document mutation, so it
holds across HTTP and MCP alike.

## D-5: Agent-run history is a pre-existing schema guarantee

`agent_runs.document_id` was declared `ON DELETE SET NULL` in the initial
migration, so a purge already keeps the audit row and nulls its reference. This
change triggers that path but does not add or alter it, and does not test it:
the only reader, `list_for_document`, cannot see a run whose reference is NULL,
so the guarantee is not observable through the ports and would diverge between
the in-memory double (which leaves the reference) and Postgres (which nulls it).
Elevating it to a normative clause here would over-claim; it stays a schema
property, noted.
