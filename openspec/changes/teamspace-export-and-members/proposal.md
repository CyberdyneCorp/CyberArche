# Export a teamspace/folder as a ZIP, and invite teamspace members

## Why

Two gaps from the sidebar:
- No way to take a whole teamspace or folder out of CyberArche — users want to
  right-click and download all its documents as a ZIP of Markdown files.
- Teamspaces support members in the backend already (add/remove/list with a
  role), but there is no UI to invite people, so others can't be given
  authoring access to a teamspace.

## What Changes

- Right-clicking a teamspace or folder gains **Export (ZIP)** — it downloads a
  ZIP containing one Markdown file per document in that scope (reusing the
  existing Markdown exporter, images inlined as data URIs).
- Add a read endpoint `GET /documents/{id}/blocks` so the client can fetch any
  document's current content (not just the open one) to render it.
- Right-clicking a teamspace gains **Manage members** — a dialog to invite a
  user (by CyberdyneAuth id, matching document sharing) with a role
  (viewer/editor/owner), list current members, and remove them. The backend
  endpoints already exist; this is the UI.

## Impact

- Affected specs: `document-export` (scope ZIP), `teamspaces` (members UI).
- Affected code: new `GET /documents/{id}/blocks` + `RealtimeUseCases.read_blocks`;
  web `jszip` dep, a scope ZIP builder, `api/documents.blocks`,
  `api/teamspaces.removeTeamspaceMember`, a `TeamspaceMembersDialog`, Sidebar
  context-menu items.
- No change to the permission model — teamspace membership + roles already exist;
  export reads only documents the caller may view.
