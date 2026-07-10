# Tasks

- [x] `ask(history=...)` threads recent (role, content) turns into the LLM messages (bounded)
- [x] `AskRequest.history` on the HTTP endpoint; router passes it through
- [x] Web: `askAgent(instruction, history)` + viewmodel sends recent turns
- [x] Prompt/tool steering: run_python for plots/results (execute+insert, not a code block); raw strings for matplotlib LaTeX
- [x] Tests: history reaches the model (backend); the chat sends recent history (vitest)
- [x] Verify: backend suite + import-linter, vitest, typecheck
