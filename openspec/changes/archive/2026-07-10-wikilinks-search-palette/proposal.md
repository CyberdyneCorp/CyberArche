# Wikilinks, search, command palette, and backlinks

## Why
CyberArche has no way to reference one document from another or to jump between
documents quickly — core to turning a pile of pages into a connected knowledge
base (and table-stakes for a Notion/Obsidian alternative). This adds the
"reference & navigate" foundation the rest of Tier 1 builds on.

## What Changes
- **Wikilinks (`[[Document Name]]`)** — typing `[[` opens an autocomplete of
  documents by title; selecting one inserts `[[Title]]`. Rendered inline as a
  clickable link that resolves, case-insensitively, to the workspace document
  with that title. An unresolved name renders as a distinct "broken/create"
  link. Resolution is by title (Obsidian-style); the raw text stays `[[Name]]`.
- **Workspace search** — a `GET /workspaces/{id}/search?q=` endpoint returns
  documents whose title matches, scoped to the caller's workspace access.
- **Command palette (Cmd/Ctrl+K)** — a global quick-switcher: search documents by
  title and jump to one, or create a new document.
- **Backlinks** — a `GET /documents/{id}/backlinks` endpoint returns the
  documents whose content references this document via `[[Title]]`, shown in a
  panel on the document. (Computed on demand by scanning workspace documents'
  block text; a link index is a later optimization.)

## Impact
- New specs: `document-links` (wikilinks + backlinks), `document-search`
  (search + palette). `block-editor`'s inline rendering gains wikilink tokens.
- Code: HTTP search + backlinks endpoints and their use cases (reusing the CRDT
  block read the agent already uses); web inline renderer (`[[…]]` tokens),
  a `[[` autocomplete in the editor, a Cmd+K palette mounted in the workspace
  layout, a backlinks panel, and a search API client.
- No data-model/migration change: title resolution and backlinks are computed
  from existing document titles and CRDT block text.
- Known limitation: backlinks/search scan documents on demand (correct, but
  O(workspace docs)); a persistent link/full-text index is a future pass.
