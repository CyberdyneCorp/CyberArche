# Tasks

## 1. LLM adapter forward-compat + reasoning
- [x] 1.1 `LLMPort.complete(..., reasoning_effort: str | None = None)`
- [x] 1.2 OpenAI adapter: `max_tokens` → `max_completion_tokens`; add `reasoning_effort` only for reasoning models (`gpt-5*`, `o1/o3/o4*`)
- [x] 1.3 Anthropic adapter + `ScriptedLLM`: accept `reasoning_effort` (Anthropic ignores; fake records it)
- [x] 1.4 Tests: adapter sends `max_completion_tokens`; sends effort for gpt-5, omits for gpt-4.1

## 2. Agent + route
- [x] 2.1 `AgentUseCases.ask(reasoning: bool)` → effort (`minimal`/`medium`) threaded to both `_llm.complete` calls
- [x] 2.2 `/ask` route: `AskRequest.reasoning` → `ask(reasoning=…)`
- [x] 2.3 Test: reasoning=True yields `medium`, False yields `minimal` at the LLM call

## 3. Chat UI toggle
- [x] 3.1 `api/agent.ts` askAgent gains `reasoning`; agent VM `ask(instruction, reasoning)`
- [x] 3.2 `AgentPanel` reasoning toggle in the composer, passed per message

## 4. Ship
- [x] 4.1 Set `CYBERARCHE_LLM_MODEL=gpt-5-mini` in Coolify
- [x] 4.2 `openspec validate gpt5-reasoning-toggle --strict`; backend + web green; deploy
