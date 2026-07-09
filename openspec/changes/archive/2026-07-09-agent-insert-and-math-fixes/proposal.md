# No duplicate insert; render TeX delimiters inline

## Why

Three issues from production:

1. Asking the agent to "create a mermaid diagram" produced an **empty block
   then the diagram**. The agent inserts live via its `insert_blocks` tool, but
   the tool only documented `data.text`, so the model put the diagram source
   under the wrong key → an empty (placeholder-only) mermaid block. And because
   the answer *also* offered a manual "Insert", clicking it added a second copy.
2. Inline math written with TeX delimiters `\(…\)` / `\[…\]` (existing content,
   and some model output) did not render — the inline renderer only handled
   `$…$`.
3. The agent panel didn't scroll to the newest answer.

## What Changes

- Block data is normalized before insert: source-based blocks (code/latex/
  mermaid) whose content the model placed under `text`/`code`/`content` are
  mapped to `source`, and a code block's language defaults — so an agent insert
  is never an empty placeholder. The `insert_blocks` tool now documents the
  per-type data schema.
- When the agent applies its edit **live** during a run (any editing tool), the
  answer carries **no** insertable blocks — the content is already in the
  document, so there is nothing to insert again (no duplicate). A conversational
  answer that made no edit still carries insertable blocks.
- The inline renderer accepts `\(…\)` and `\[…\]` in addition to `$…$`.
- The agent panel auto-scrolls to the latest message.

## Non-goals

- Changing when the agent chooses to edit live vs. answer — only the
  double-application is removed.

## Impact

- `ai-agent`: "Every answer yields insertable blocks" gains the live-edit
  exception.
- `block-editor`: inline-math rendering covers TeX delimiters.
- Frontend-only auto-scroll; backend block normalization.
