# AI "continue writing" (ghost-text autocomplete)

## Why

The editor has no AI continuation. The only inline autocomplete is `[[`
wikilinks. A Copilot/Notion-AI style ghost text — pause typing, the LLM proposes
the next sentence, Tab to accept — is the single most "magic" editor feature
still missing, and the tool-free LLM plumbing shipped for inline transforms
makes it cheap.

## What Changes

- Add `AgentUseCases.continue_writing(caller, document_id, *, preceding_text)`: a
  single tool-free LLM call that returns a short continuation of the given text.
  Requires view access; returns text only (no document edits).
- New endpoint `POST /documents/{id}/agent/continue`.
- Editor: debounced ghost-text suggestion at the caret (end of a block), shown
  as dimmed inline text; Tab accepts (inserted through the CRDT edit path, so
  undoable), Escape/typing dismisses.

## Impact

- Affected specs: `ai-agent`.
- Affected code: `use_cases/agent.py` (continue_writing), agent router; editor VM
  ghost-text state + EditableText rendering + `api/agent.ts`. No migration.
