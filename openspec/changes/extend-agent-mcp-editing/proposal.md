# MCP positional insert + replace; agent summarize-a-selection

## Why

Two clauses are stated but only partly built:

- `mcp-server` "Document tools" promises editing as "append/**insert/replace**
  blocks," but the only edit tool is `insert_blocks`, which appends. There is
  no way over MCP to insert at a position or to replace a block's content — so
  an external assistant (Claude, ChatGPT) can only add to the end of a document.
- `ai-agent` "Summarize and draft" promises summarizing "a document **or
  selection**," but `AgentUseCases.summarize` takes only a document id and
  always summarizes the whole thing.

Both had a scenario for the implemented half only, so the missing half passed
`--strict` unnoticed — the class we have been closing all session.

## What Changes

- Engine: `insert_blocks_after(state, after_id, blocks)` (positional insert) and
  `replace_block(state, block_id, block)` (full type+data replacement of one
  block). The whole-body `replace_blocks` already exists (snapshot restore).
- Agent use cases gain positional insert and single-block replace, both applied
  through the realtime seam like every other agent edit (attributed, live).
- MCP `insert_blocks` gains an optional `after_block_id`; a new MCP tool
  `replace_block` replaces a block's content. Both enforce editor permission
  through the same use cases HTTP uses.
- `AgentUseCases.summarize` gains an optional `block_ids`: when given, the
  summary is scoped to those blocks.

## Non-goals

- Exposing delete over MCP (separate; the agent has it internally).
- Rich diffing or partial-text replacement — replace swaps a whole block.

## Impact

- `mcp-server`: the "insert/replace" half of Document tools gains scenarios.
- `ai-agent`: Summarize gains a selection scenario.
- Engine port grows two methods; covered by the CRDT engine test suite.
