# Tasks

## Backend — capability
- [x] `ports/code_exec.py`: `CodeExecutionPort`, `CodeExecutionResult`, `CodeImage`
- [x] `adapters/outbound/code_exec/cyberdyne_interpreter.py`: session → execute → download images; figure-capture epilogue; parse rich_outputs/artifacts
- [x] `ScriptedCodeExecutor` fake for tests

## Backend — agent tool
- [x] Inject `code` into `AgentUseCases`; `run_python` tool spec + dispatch + handler (store figures as image blocks, return textual output); unavailable-fallback
- [x] Mention Python execution in the system prompt

## Backend — wiring/config
- [x] `interpreter_base_url` in WiringConfig; build adapter with the service-token source; `build_container` injectable; `CYBERARCHE_INTERPRETER_URL` setting

## Backend tests
- [x] `run_python` inserts image block(s) + returns stdout/result (fake executor); unavailable when unconfigured
- [x] figure-capture epilogue is appended only for unsaved matplotlib code

## Verify
- [x] Backend suite + import-linter; typecheck/vitest/e2e regression (no FE change)
