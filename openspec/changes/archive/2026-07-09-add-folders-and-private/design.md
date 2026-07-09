# Design

## D-1: Private = teamspace-less, creator-only

The smallest change that yields a private space: a document with `teamspace_id =
NULL` is private to its `created_by`. `AccessControl.document_role` returns the
document grant if one exists, else `owner` when the caller is the creator, else
`None` — the workspace role is **not** consulted for a private document. A
document with a teamspace is unchanged: strongest(workspace, teamspace, grant),
grant overriding. This confines the permission change to teamspace-less docs and
leaves teamspace collaboration exactly as it was.

## D-2: A folder carries the teamspace scope; a document inherits it

Rather than compute a document's effective teamspace through a chain of parent
folders on every permission check, a document's own `teamspace_id` always
reflects its scope. Placing a document in a folder sets the document's
`teamspace_id` to the folder's; moving it to the private space clears it. So
`document_role` keeps reading `document.teamspace_id` — no folder lookups in the
hot path — and `folder_id` is purely organizational (which container the sidebar
shows it under).

## D-3: Folder visibility mirrors document visibility

A folder in a teamspace is visible to that teamspace's members; a private folder
(no teamspace) is visible only to its creator. Listing a workspace's folders
returns the teamspaces the caller can see plus the caller's own private folders.

## D-4: Deleting a container never destroys documents

`documents.folder_id` is `ON DELETE SET NULL`: deleting a folder detaches its
documents (they fall back to the folder's teamspace, or to private) rather than
trashing them — the same principle as teamspace deletion (0006 D-5). Nested
folders cascade (`parent_folder_id ON DELETE CASCADE`).

## D-5: Migration leaves existing docs private to their creator

Existing teamspace-less documents already have `teamspace_id = NULL`, so under
D-1 they become private to whoever created them — which matches "these were your
loose documents". No data moves; only the access rule changes.
