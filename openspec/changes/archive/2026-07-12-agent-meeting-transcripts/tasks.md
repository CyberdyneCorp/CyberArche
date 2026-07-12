# Tasks

## 1. Port + adapter
- [x] 1.1 `application/ports/meetings.py`: `MeetingsPort` (list_recordings, get_recording, ask), taking a per-call access token
- [x] 1.2 `adapters/outbound/meetings/cyberflies.py`: HTTP adapter (bearer = caller token), parse recordings/transcript/summary/chat
- [x] 1.3 Unit test: adapter maps Cyberflies JSON → port results, sends the caller token as bearer

## 2. Token threading (delegated auth)
- [x] 2.1 `dependencies.py`: expose the raw bearer token as a dependency (`AccessToken`)
- [x] 2.2 `agent.py` `/ask` route: pass `access_token` to `cases.agent.ask`
- [x] 2.3 `AgentUseCases.ask` → `_run_loop` → `_available_tools`/`_dispatch`: thread `access_token`; never log/store it

## 3. Agent tools
- [x] 3.1 `list_meetings`, `get_meeting_transcript`, `ask_meetings` specs; offered only when meetings port set AND token present
- [x] 3.2 Dispatch handlers → `MeetingsPort`; return text, tolerate 401/403/errors gracefully
- [x] 3.3 `_classify_tool` treats them as builtin (read-only, not editing)

## 4. Wiring + config
- [x] 4.1 `WiringConfig.meetings_base_url` + `Settings.meetings_url` (default Cyberflies URL) + `wiring()` map
- [x] 4.2 `_build_meetings` + pass `meetings=` into `AgentUseCases`
- [x] 4.3 docker-compose: `CYBERARCHE_MEETINGS_BASE_URL`

## 5. Tests + validate
- [x] 5.1 Agent tests: list/get/ask via a fake MeetingsPort; token forwarded; unavailable when unconfigured; unavailable without a token
- [x] 5.2 `openspec validate agent-meeting-transcripts --strict`; backend tests + import-linter green
