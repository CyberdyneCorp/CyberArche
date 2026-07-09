# Tasks

## 1. Backend: typed blocks
- [x] 1.1 `_answer_blocks(ids, text)` parser: fenced code/mermaid, display math ($$ / \[ \]) -> latex, prose paragraphs with \( \) -> $ $ inline
- [x] 1.2 Use it in ask/summarize/draft (replace `_paragraph_blocks`)
- [x] 1.3 System prompt: steer the model to $…$/$$…$$, ```mermaid, ```lang
- [x] 1.4 Tests: code/mermaid/latex/paragraph detection, \[ \] -> latex, \( \) -> inline $, plain prose unchanged

## 2. Frontend: insert locally
- [x] 2.1 Editor VM `insertBlocks(blocks)`: append typed blocks to the local doc (CRDT peer), one undo step
- [x] 2.2 Agent panel Insert calls the editor VM (not HTTP); pass the editor to the agent panel
- [x] 2.3 vitest: editor.insertBlocks appends typed blocks; e2e: insert shows immediately
