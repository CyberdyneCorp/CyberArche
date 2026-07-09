# Surface agent tool calls in chat

## Why
The agent runs tools (RAG search, document edits, image generation, external
MCP servers) but the chat only shows the final text answer. Users can't see what
the agent actually did or inspect a tool's inputs/outputs — unlike Claude's UI,
which lists each tool call and lets you expand it. The backend already has the
name, arguments, and result for every call in the run loop; it just discarded
them.

## What Changes
- `ask` captures each tool call it makes — name, kind (`builtin` | `editing` |
  `mcp`), the MCP connector slug where applicable, the arguments, the result, and
  whether it succeeded — and returns them alongside the answer.
- The `/ask` response gains a `tool_calls` array.
- The chat renders each answer's tool calls as expandable entries (Claude-style):
  a one-line summary with an icon + name + kind badge, expanding to show the
  input arguments and the output. Failed calls are flagged.
- Results are truncated to keep the payload bounded.

## Impact
- Modified spec: `ai-agent` (answers surface their tool calls).
- Code: `use_cases/agent.py` (`AgentAnswer.tool_calls`, `_run_loop` capture,
  `_classify_tool`), `routers/agent.py` (`ToolCallResponse`), web `api/agent.ts`,
  `viewmodels/agent.svelte.ts`, `AgentPanel.svelte`.
- No persistence change: tool calls are returned for the live answer only, not
  stored on the audit run (which keeps its tool-name list).
