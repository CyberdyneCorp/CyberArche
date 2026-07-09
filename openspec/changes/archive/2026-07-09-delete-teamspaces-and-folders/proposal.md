# Delete teamspaces and folders

## Why
The sidebar can create teamspaces and folders but not delete them. Users need to
remove a teamspace or folder along with the documents inside it. Deletion is
destructive, so it must be confirmed — and the app currently confirms with the
browser's native `confirm()`/`prompt()`, which is jarring and unstyled. We want
an in-app confirm dialog and toast notifications instead.

## What Changes
- **Delete a teamspace** (new): an owner can delete a teamspace. Its documents
  (including those in its folders) move to Trash — recoverable, not purged — and
  its folders are removed. Add the use case, repository `delete`, and
  `DELETE /api/v1/teamspaces/{id}`.
- **Delete a folder moves its documents to Trash** (behavior change): deleting a
  folder previously *detached* its documents (cleared `folder_id`, kept them
  live). It now moves the folder's documents — across its sub-folders — to Trash,
  matching the teamspace behavior and the user's mental model of "delete
  including all documents".
- **In-app confirm dialog** (new): a promise-based confirm/prompt replaces native
  `confirm()`/`prompt()`. Destructive confirms are styled distinctly.
- **Toasts** (new): a global toast container surfaces success/error messages
  (e.g. "Teamspace deleted", "Couldn't delete folder").
- **Sidebar delete affordance** (new): a kebab (⋯) menu on hover *and* right-click
  on a teamspace/folder row open a menu with Delete.

## Impact
- Affected specs: `teamspaces` (delete), `folders` (lifecycle behavior change)
- Affected code: `application/use_cases/teamspaces.py`, `use_cases/folders.py`,
  `ports/teamspaces.py`, in-memory + Postgres teamspace repos, HTTP
  `routers/teamspaces.py`, wiring; web `api/teamspaces.ts`, new `toasts` and
  `dialogs` viewmodels + `Toasts.svelte`/`ConfirmDialog.svelte`/`ContextMenu.svelte`,
  `Sidebar.svelte`, root `+layout.svelte`.
- Destructive: documents move to Trash (recoverable). Teamspace delete requires
  the OWNER role; folder delete requires EDITOR on the folder.
