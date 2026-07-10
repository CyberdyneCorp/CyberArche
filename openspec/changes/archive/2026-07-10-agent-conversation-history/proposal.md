# Agent conversation history + tool steering

## Why
The chat agent was **stateless**: each `ask` sent only the system prompt, the
document's current blocks, and the latest instruction — no prior turns. So a
follow-up like "insert the plot" had no referent; the model confabulated
(inserting unrelated code it invented, or grabbing stale blocks from the
document). Separately, when asked to "create a plot" the model often inserted the
Python as a *code block* (`insert_blocks`) instead of running it via `run_python`
(which executes and inserts the figure).

## What Changes
- **Conversation history:** `ask` accepts recent `(role, content)` turns and
  includes them in the LLM messages (capped to the last N, each truncated), so
  follow-ups continue the conversation. The web chat sends its recent turns with
  each request.
- **Tool steering (prompt):** the system prompt and the `run_python` tool
  description now tell the model to use `run_python` (execute + insert the figure)
  when the user wants to see a plot/result, rather than pasting a code block, and
  to use raw strings for LaTeX in matplotlib labels.

## Impact
- Modified spec: `ai-agent` (conversation continuity).
- Code: `use_cases/agent.py` (`ask(history=...)`, prompt), HTTP `AskRequest.history`,
  web `api/agent.ts` + `agent.svelte.ts`. No new endpoints; history is per-request
  (the client owns the transcript), so no server-side session storage.
