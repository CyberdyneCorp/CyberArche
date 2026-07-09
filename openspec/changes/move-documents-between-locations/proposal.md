# Move documents between locations

## Why
Documents could be placed in a folder or moved to the private space, but there
was no way to move a document **directly into a teamspace** (without a folder),
and the sidebar only exposed placement for private documents. Users asked to
drag documents onto a teamspace or folder to reorganize them, and to star,
trash, and add child documents to docs that live inside teamspaces and folders —
not just in the Private section.

## What Changes
- Add a `move_to_teamspace` use case: moving a document to a teamspace sets its
  teamspace and clears any folder reference, so it lives loose under that
  teamspace.
- Replace the placement HTTP endpoint `POST /api/v1/documents/{id}/folder` with a
  single `POST /api/v1/documents/{id}/location` that accepts a `folder_id`, a
  `teamspace_id`, or neither (→ private).
- Sidebar: documents are draggable onto teamspace and folder rows and onto the
  Private section; dropping calls the appropriate placement. Teamspace and folder
  document rows gain star / add-child / trash actions, matching the Private tree.
- Enlarge the teamspace/folder disclosure caret so it is easier to hit.

## Impact
- Affected specs: `document-model` (placement), `folders` (sidebar placement UX)
- Affected code: `application/use_cases/documents.py`, HTTP `routers/folders.py`,
  web `api/folders.ts`, `Sidebar.svelte`, `TreeItem.svelte`
- Breaking: the `/documents/{id}/folder` endpoint is renamed to `/location`
  (internal API; the web client is updated in the same change).
