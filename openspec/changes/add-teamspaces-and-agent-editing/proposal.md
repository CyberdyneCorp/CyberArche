## Why

Four gaps surfaced from using the deployed product:

1. **A block cannot be deleted.** The gutter offers add / move / comment, but
   nothing removes a block — the only escape is emptying it and pressing
   Backspace.
2. **The agent cannot edit the open document.** It has exactly two tools
   (`rag_query`, `read_document`), so "add the text Hello World to that block"
   fails; it reaches for `read_document`, passes the title instead of an id,
   and reports it cannot access the document. Only the hardcoded
   `Draft section` action can produce content.
3. **Conversational answers cannot be inserted.** `ask` returns plain text
   with no blocks, so the panel shows no insert affordance — the user must
   copy by hand.
4. **No workspace switcher and no Teamspaces.** A workspace is reachable only
   by URL, and documents cannot be grouped into a team-owned space with its
   own membership.

## What Changes

- **Teamspaces**: a named, member-scoped grouping of documents inside a
  workspace. Create, list, add/remove members, and place documents in a
  teamspace. Access to a teamspace's documents flows from teamspace
  membership in addition to workspace role.
- **Agent document editing**: the agent gains `insert_blocks`,
  `update_block`, and `delete_block` tools bound to the open document,
  applied through the CRDT as a peer (live, attributed, undoable).
- **Conversational insert**: every agent answer carries insertable blocks;
  the panel exposes Insert / Replace-selection / Copy actions per message.
- **Block delete** affordance in the editor gutter, undoable.
- **Sidebar**: workspace switcher (current workspace, new workspace,
  settings), plus Favorites, Teamspaces, and Shared-with-me sections.
- **Favorites**: a user can favourite a document.

## Capabilities

### New Capabilities

- `teamspaces`: team-owned groupings of documents inside a workspace, with
  membership-derived access.
- `favorites`: per-user document favourites.

### Modified Capabilities

- `ai-agent`: the agent can modify the open document through tools, and every
  answer yields insertable blocks.
- `block-editor`: blocks can be deleted from the gutter.
- `document-model`: a document may belong to a teamspace.
- `permissions-sharing`: teamspace membership grants access to its documents.

## Impact

- **Domain**: `Teamspace`, `TeamspaceMembership`, `Favorite`; `Document`
  gains `teamspace_id`.
- **Application**: `TeamspaceRepository`/`FavoriteRepository` ports,
  `TeamspaceUseCases`, `FavoriteUseCases`; `AccessControl` consults teamspace
  membership; agent tool registry gains document-bound editing tools.
- **Adapters**: `CrdtEnginePort` gains `update_block` / `delete_block`;
  Postgres adapters + migration `0006_teamspaces_favorites`; HTTP routers.
- **Web**: sidebar restructure (switcher, Favorites, Teamspaces, Shared),
  block delete button, agent message action icons.
