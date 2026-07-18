# Tasks
- [ ] 1.1 `AgentUseCases.continue_writing` — tool-free LLM call, view-scoped, returns a short continuation only
- [ ] 1.2 `POST /documents/{id}/agent/continue` endpoint
- [ ] 1.3 Editor ghost text: debounced request at caret, dimmed inline suggestion, Tab accepts (CRDT-applied, undoable), Escape/edit dismisses
- [ ] 1.4 Tests: continuation returns text, view required, empty preceding-text guard; frontend accept/dismiss + debounce
- [ ] 1.5 `openspec validate continue-writing --strict`; gates green
