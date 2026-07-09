# Tasks

## 1. Engine
- [x] 1.1 `insert_blocks_after(state, after_id, blocks)` — insert after a block; NotFound if the id is absent
- [x] 1.2 `replace_block(state, block_id, block)` — replace one block's type+data; NotFound if absent
- [x] 1.3 Engine tests: insert-after position + order, replace type change, unknown-id raises

## 2. Agent use cases
- [x] 2.1 `insert_blocks(caller, doc, blocks, after_id=None)` through realtime.apply
- [x] 2.2 `replace_block(caller, doc, block_id, block)` through realtime.apply
- [x] 2.3 `summarize(caller, doc, block_ids=None)` — scope the instruction to the selection when given
- [x] 2.4 Tests: insert-at-position, replace, permission refused, summarize-selection names the blocks

## 3. MCP tools
- [x] 3.1 `insert_blocks(document_id, blocks, after_block_id=None)`
- [x] 3.2 `replace_block(document_id, block_id, block)`
- [x] 3.3 MCP tests over the in-memory server: insert-at-position, replace, view-only refused
