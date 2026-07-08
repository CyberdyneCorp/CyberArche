## Context

Four gaps from real use of the deployed product (see proposal). The agent's
inability to edit is the root of two of them: `AgentUseCases` registers exactly
two tools (`rag_query`, `read_document`), so an edit request makes the model
guess at `read_document` with a title and give up. `ask()` also returns bare
text, so no insert affordance can be offered.

## Goals / Non-Goals

**Goals:** teamspaces with membership-derived access; agent write access to the
open document through the CRDT; insertable answers; a block delete control;
sidebar switcher/Favorites/Teamspaces/Shared.

**Non-Goals:** teamspace-scoped RAG projects (knowledge stays per workspace);
nested teamspaces; per-block ACL; teamspace-level share links.

## Decisions

### D-1 — Effective role = strongest of workspace / teamspace, then document override
`AccessControl` resolves the workspace role and the teamspace role (if the
document has one) and takes the stronger; an explicit document grant still wins
outright, preserving the existing "more specific grant" rule. **Rationale:**
teamspaces must *grant* access to people who lack a workspace role (the Tessera
model) without silently escalating someone a document grant deliberately
demoted. **Alternative rejected:** teamspace membership replacing workspace
role — would demote workspace owners inside a teamspace they don't belong to.

### D-2 — Agent editing tools are bound per run, not globally registered
`ToolRegistry` stays the process-wide surface for context-free tools. Editing
tools (`insert_blocks`, `update_block`, `delete_block`) are constructed per
`ask()` with the document id captured in the closure, appended to the specs
offered to the model, and dispatched before the global registry. **Rationale:**
the model cannot address another document even if it hallucinates an id, and no
mutable per-request state leaks into a shared registry. Permission is checked in
`apply_blocks`/`realtime.apply` exactly as for human edits.

### D-3 — CRDT engine gains `update_block` / `delete_block`
The engine already owns the `Array("blocks")` convention; update and delete are
expressed there as incremental updates against the current state, so agent and
human edits stay symmetric and merge conflict-free. `update_block` merges into
the block's `data` map rather than replacing it, so a text edit does not drop a
whiteboard scene.

### D-4 — Every answer is turned into blocks
`ask()` returns `(text, blocks)`; blocks are the paragraph split of the answer
(the existing `_paragraph_blocks`). The panel offers Insert / Replace-selection
/ Copy per message. **Trade-off:** an answer containing code or a table is
inserted as paragraphs; richer conversion is deferred.

### D-5 — Teamspace is a first-class row, favourites a join table
`teamspaces` (workspace-scoped) + `teamspace_memberships`; `documents` gains a
nullable `teamspace_id` (FK, `ON DELETE SET NULL` so deleting a teamspace never
destroys documents). `favorites(user_id, document_id)` is a per-user join,
never exposed across users.

## Risks / Trade-offs

- Effective-role resolution now reads one extra membership row per document
  authorization → cache the teamspace role per request; it is a keyed lookup.
- Agent edits are undoable only by the human's `Y.UndoManager` when the doc is
  open; an edit applied while nobody is connected is durable → the agent-run
  audit records what changed.
- Deleting a teamspace orphans its documents to workspace level (by design,
  `SET NULL`) rather than deleting content.

## Migration Plan

Additive migration `0006_teamspaces_favorites`: two new tables, one nullable
column on `documents`. No backfill; existing documents remain workspace-level.
Rollback: drop the column and tables (access reverts to workspace/document
grants).
