# Dedicated folders; teamspace-less docs are private to their creator

## Why

Documents are workspace-global today: the "+ New document" button creates a
teamspace-less document, and the sidebar lists all such docs in a flat
"Documents" section visible to every workspace member. There is no way to keep a
document private, and no container to organize documents beyond ad-hoc page
nesting. The intended hierarchy is Workspace → Teamspace → Folders → Documents,
plus a private space per user.

## What Changes

- **Private space.** A document with no teamspace is *private*: only its creator
  (or an explicit document grant) may access it — a workspace role no longer
  grants access to teamspace-less documents. Documents inside a teamspace are
  unchanged (workspace + teamspace roles still apply). The sidebar's flat
  "Documents" section becomes "Private", listing only the caller's own
  teamspace-less documents.
- **Folders.** A dedicated `folder` entity (not a document) groups documents and
  sub-folders. A folder lives in a teamspace (shared with its members) or in the
  private space (creator-only), and may nest. A document may be placed in a
  folder; it then takes the folder's teamspace scope, so permissions follow the
  container.

## Non-goals

- Changing how workspace/teamspace roles combine for teamspace documents.
- Drag-and-drop reordering across containers (a later pass); placement is via an
  explicit action.

## Impact

- New `folders` table + `documents.folder_id`; migration.
- `permissions-sharing`: the "Roles" requirement gains the private rule.
- `document-model`: documents may belong to a folder.
- New `folders` capability. AccessControl, document listing, and the sidebar
  change. Contract + use-case + e2e tests.
