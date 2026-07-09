# Tasks

## Backend
- [x] `AgentAnswer.tool_calls` + `ToolCallLog`; capture name/kind/connector/arguments/result/ok in `_run_loop`
- [x] `_classify_tool` (mcp via `slug__` namespace, editing set, else builtin); truncate result
- [x] `/ask` returns `tool_calls` (`ToolCallResponse`)
- [x] Tests: classifier; `ask` returns captured calls with kinds/arguments/result

## Frontend
- [x] `AgentToolCall` type + `tool_calls` on `AskResult`; map to `AgentMessage.toolCalls`
- [x] AgentPanel renders expandable tool calls (icon + name + kind badge; input/output; failure flag)
- [x] Vitest: VM surfaces built-in + MCP calls with ok flags

## Verify
- [x] Backend suite + import-linter, vitest, typecheck; e2e regression
