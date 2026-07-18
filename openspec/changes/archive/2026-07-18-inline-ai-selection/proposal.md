# Inline "Ask AI" on selection

## Why

The agent lives in a side panel and the workspace chat is separate — there's no
way to transform text *in place*. Selecting text and asking AI to rewrite /
shorten / expand / fix / translate it is the highest daily-use editing action a
modern editor has, and the LLM + editor selection handling already exist.

## What Changes

- Add `AgentUseCases.transform_text(caller, document_id, *, text, action,
  target=None)`: a single, tool-free LLM call that returns the transformed text
  for one action (`rewrite`, `shorten`, `expand`, `fix`, `translate`). Requires
  view access; returns only the transformed text (no document edits — the user
  applies it).
- New endpoint `POST /documents/{id}/agent/transform`.
- Editor: a selection (bubble) menu with an **Ask AI** group offering the
  actions; the result replaces the selected text (with an undo-friendly apply).

## Impact

- Affected specs: `ai-agent`.
- Affected code: `use_cases/agent.py` (transform_text), agent router; a
  `SelectionMenu` component + editor wiring + `api/agent.ts`. No migration.
