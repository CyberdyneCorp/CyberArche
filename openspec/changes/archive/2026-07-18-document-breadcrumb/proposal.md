# Document breadcrumb path

## Why

An open document shows only its title in the top bar, with no indication of where
it lives. Users can't see or navigate the containing workspace, teamspace,
folder, or parent documents. A breadcrumb path (Workspace / Teamspace / Folder /
… / Title) gives location and one-click navigation up the hierarchy.

## What Changes

- Add `DocumentUseCases.path(caller, document_id)` returning the ordered ancestor
  chain as crumbs: the workspace, then the teamspace (if any), then the folder
  chain (root→leaf, if foldered), then ancestor documents (root→parent), then the
  document itself — each crumb a kind, id, and label. View-access scoped.
- New endpoint `GET /api/v1/documents/{id}/path`.
- The document top bar renders the crumbs, with the workspace and ancestor
  documents navigable; the current document is the final, non-link crumb.

## Impact

- Affected specs: `document-model`.
- Affected code: `DocumentUseCases` (path + a workspace-repo dep), documents
  router; frontend api client + the document header breadcrumb. Read-only; no
  migration.
