# GPT-5 support + a chat reasoning toggle

## Why

We want to move the agent to `gpt-5-mini` (better agentic tool-calling and code
than `gpt-4.1-mini` at comparable cost). Two blockers/opportunities:

- The OpenAI-compatible adapter sends `max_tokens`, which the GPT-5 family (and
  o-series) reject — they require `max_completion_tokens`. Switching to
  `max_completion_tokens` is forward-compatible (gpt-4.1/gpt-4o accept it too).
- GPT-5 models take a `reasoning_effort`. Rather than fix it server-side, let the
  user decide per message with a **Reasoning** toggle in the chat window: off =
  fast/cheap (`minimal`), on = deeper (`medium`).

## What Changes

- LLM port `complete()` gains an optional `reasoning_effort`. The
  OpenAI-compatible adapter sends `max_completion_tokens` instead of
  `max_tokens`, and includes `reasoning_effort` only for reasoning-capable models
  (so it never breaks non-reasoning models like gpt-4.1). The Anthropic adapter
  accepts the argument and ignores it.
- `AgentUseCases.ask` gains `reasoning: bool`; it maps to `reasoning_effort`
  (`minimal` when off, `medium` when on) and threads it to the LLM calls.
- The `/ask` route accepts `reasoning`, and the chat window gains a Reasoning
  toggle that sets it per message.
- Switch the deployed chat model to `gpt-5-mini` (`CYBERARCHE_LLM_MODEL`).

## Impact

- Affected specs: `ai-agent` (per-request reasoning effort + forward-compatible
  token parameter).
- Affected code: `ports/llm`, `openai_compatible`, `anthropic`, `ScriptedLLM`,
  `AgentUseCases.ask`/`_run_loop`, `/ask` route + `AskRequest`; web `api/agent`,
  agent VM, `AgentPanel`.
- Ops: `CYBERARCHE_LLM_MODEL=gpt-5-mini`. No schema/auth change.
