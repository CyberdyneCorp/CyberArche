# Agent access to meeting transcripts (Cyberflies)

## Why

Cyberflies (https://cyberflies.backend.coolify.cyberdynecorp.ai) records and
transcribes the user's meetings. Users want the CyberArche agent to pull their
own meeting transcripts and summaries into a document ("add the transcript of my
last standup", "what were the action items from my meetings this week?").

Cyberflies authenticates with the **same CyberAuth identity** as CyberArche and
its API is strictly per-user ("my recordings"). So the secure, zero-setup model
is delegated auth: the agent forwards the **caller's own access token** to
Cyberflies during the chat request, and Cyberflies enforces access — the agent
can only ever read what that user is already entitled to (their recordings plus
meetings shared with them through Cyberflies channels). No cross-user access, no
impersonation, no stored secrets.

## What Changes

- Add a `MeetingsPort` and a Cyberflies HTTP adapter that reads recordings and
  transcripts and answers meeting questions, authenticating with a per-request
  caller access token (never a service token — the data is per-user).
- Thread the caller's access token from the `/ask` HTTP route through
  `AgentUseCases.ask` to tool dispatch, as an explicit delegation credential
  (not added to `CallerContext`, which stays claims-only).
- Add three read-only agent tools, offered only when Cyberflies is configured
  AND a caller token is present:
  - `list_meetings` — recent recordings (id, captured time, status, headline).
  - `get_meeting_transcript` — a recording's transcript text + summary (headline,
    abstract, bullets, action items) by id.
  - `ask_meetings` — a natural-language question answered across the user's
    meetings (Cyberflies `POST /chat`).
- The tools return text; the agent composes it (e.g. `insert_blocks`) — they do
  not themselves edit the document.
- Config: `CYBERARCHE_MEETINGS_BASE_URL` (defaults to the Cyberflies URL); empty
  disables the tools.

## Impact

- Affected specs: `ai-agent` (new meeting-transcript tools + delegated auth).
- Affected code: new `application/ports/meetings.py`; new
  `adapters/outbound/meetings/cyberflies.py`; `AgentUseCases`
  (`ask`/`_run_loop`/`_available_tools`/`_dispatch` gain the token + tools);
  `agent.py` HTTP route (extract + pass the bearer token); wiring + config +
  docker-compose env.
- Security: the caller's access token is forwarded only to the single configured
  Cyberflies base URL, only on the interactive `/ask` path, and is never logged
  or stored (audit records tool name + arguments, not the token). Cyberflies
  performs authorization.
- No change to `CallerContext`, the realtime transport, or persistence.
