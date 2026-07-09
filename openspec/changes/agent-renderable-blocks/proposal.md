# Agent answers become typed blocks; Insert applies locally

## Why

Two problems reported from production:

1. The agent's answers are turned into blocks by splitting the text on blank
   lines into **paragraphs only** (`_paragraph_blocks`). So when the agent
   returns LaTeX (`\[ … \]`), a Mermaid diagram, or code, inserting it drops raw
   source text into paragraphs that the editor cannot render — the agent
   "isn't aware of" Mermaid/LaTeX. The editor already has `latex`, `mermaid`,
   and `code` blocks; the answer just never becomes them.
2. "Insert" posts the blocks to the server (`apply_blocks`), which applies them
   to the CRDT and broadcasts over the WebSocket. If the client's socket is
   offline, the edit is applied server-side but the user never sees it — the
   button says "Inserted" while the document stays empty.

## What Changes

- The agent parses its answer into typed blocks: fenced ```mermaid → a `mermaid`
  block, ```lang → a `code` block, display math (`$$…$$` or `\[…\]`) → a `latex`
  block, and prose → paragraphs with `\(…\)` normalized to inline `$…$`. Used by
  ask/summarize/draft. Inline `$…$` in prose is preserved for the inline renderer.
- The system prompt tells the model to express math with `$…$`/`$$…$$`, diagrams
  as ```mermaid fences, and code as ```lang fences, since the editor renders those.
- "Insert" applies the blocks to the **local** editor document (a CRDT peer
  edit) instead of posting to the server. They appear immediately and sync when
  the connection is up — offline no longer hides the insert, and there is no
  double-apply.

## Non-goals

- Rewriting the agent's editing tools (insert_blocks/update_block over MCP/HTTP)
  — those stay for programmatic/live edits; this is about the *answer → insert*
  path in the panel.
- Full Markdown parsing (tables, nested lists) — headings, code, mermaid, math,
  and paragraphs cover the reported gap.

## Impact

- `ai-agent`: "Every answer yields insertable blocks" gains typed-block scenarios.
- Backend: `_answer_blocks` parser replaces `_paragraph_blocks`; system prompt
  updated. Frontend: the panel's Insert uses the editor VM, not HTTP.
