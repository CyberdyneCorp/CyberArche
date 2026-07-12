# Design — Autonomous scheduled agents

## Context

CyberArche agent runs are currently interactive only: an inbound HTTP/MCP
adapter resolves a `CallerContext` from a verified user token and calls
`AgentUseCases.ask(caller, document_id, instruction=…, access_token=…)`, which
drives `_run_loop()` over the LLM + tool registry. This change adds a
*non-interactive* path: a scheduler fires a task with no live user, so we must
solve (1) how the service authenticates outbound, (2) whose authority the run
carries, (3) how to run it safely without a human to confirm, and (4) how the
result reaches a document and the user.

Facts we build on:
- `CallerContext` already carries `user_id`, `tenant_id`, `scopes`, `is_service`.
- `ClientCredentialsTokenSource` already exists in
  `adapters/outbound/auth/cyberdyne.py` (used for RAG + introspection). We reuse
  it as the transport credential source; we do **not** reuse its *identity* for
  authorization.
- `AgentRunRepository` / `AgentRun` (`ports/agent.py`) already audit interactive
  runs; we extend the same area with a task-run audit type.
- The agent's destructive editing tools are enumerated (`delete_block`, and the
  document-delete path); `_EDITING_TOOL_NAMES` already classifies editing tools.

## Decision 1 — Service-token acquisition & caching (outbound transport)

A background run must call sibling backends (CyberRAG `cyberrag:query`, the code
interpreter `interpreter:execute`) but has no user bearer. CyberArche
authenticates **as itself** with the OAuth2 client-credentials grant:

- `POST https://<cyberdyne-auth>/api/v1/auth/oauth2/token`
- `grant_type=client_credentials`, `client_secret_basic` auth (client id/secret
  in the HTTP Basic header), `scope="cyberrag:query interpreter:execute"`, and
  optionally `audience`.
- The returned token has `type=service`, `sub=client:<id>`, carries `scope`, and
  TTL ~1h. Sibling backends verify it (self-verify JWT or `/introspect`).

Caching: reuse/extend `ClientCredentialsTokenSource` — cache the token in memory
and refresh when within a safety margin (≈30s) of expiry. One token source per
process, shared by the scheduler and the run. This is documented as a new
requirement on the `auth-integration` capability; it is **distinct** from the
existing generic "Service-to-service authentication" requirement in that it
pins CyberArche's own client-credentials acquisition, caching, and the scopes
needed for background agent work.

## Decision 2 — Owner-scoped authorization (the auth-critical decision)

The service token is `client:<id>`; it has **no end-user identity** and (if
trusted as the actor) would grant service-wide reach across every tenant. That
must never be the authority for a run. Instead:

- Each `ScheduledAgentTask` stores its **owner** (`owner_id`) and `tenant_id` at
  creation, captured from the verified user token of the creator.
- At run time the scheduler builds a `CallerContext` from the **stored owner**:
  `user_id = owner_id`, `tenant_id = task.tenant_id`, `is_service = False` for
  authorization purposes (it is a real user's authority, merely executed by the
  service). The run flows through the exact same `AccessControl` checks
  (`require_document`, `require_workspace`) as an interactive run.
- The Postgres session sets `cyberarche.tenant_id = task.tenant_id` so RLS scopes
  every query to the owner's tenant.
- The service token is attached **only** to outbound calls to sibling services as
  transport (the `access_token` passed into `_run_loop` for RAG/interpreter),
  never mapped into the `CallerContext` identity.
- **Re-check at run time:** if the owner has since lost access to the target
  document/workspace, `AccessControl` denies and the run is recorded as
  `denied` — authority is evaluated against the owner's *current* permissions,
  not a snapshot from task-creation time.

This cleanly separates *who authorizes the work* (stored owner) from *what
credential talks to siblings* (service token), matching the contrast with
interactive tools, which forward the caller's own user bearer and never mint a
service token.

## Decision 3 — Scheduler shape & single-run locking

Pragmatic for single-instance Coolify, but safe if replicated:

- A periodic scheduler wakes on a fixed tick (e.g. every 60s). Two viable shapes,
  both acceptable; the tasks list the in-process option as default:
  1. **In-process asyncio loop** started alongside uvicorn in the API's lifespan
     (simplest for a single instance), or
  2. **A separate `services/cyberarche/workers` entrypoint** (`cyberarche-agent-scheduler`)
     invoked by the Docker `command:`, mirroring the existing `cyberarche-workers`
     deployable. Migrations already run before uvicorn via `scripts/migrate.py`,
     so the scheduler can assume the schema exists.
- On each tick the scheduler selects tasks whose `enabled = TRUE` and whose
  `next_run_at <= now()` (cron computed) or whose trigger fired.
- **Single-run locking:** claim a due task atomically with
  `SELECT … FOR UPDATE SKIP LOCKED` (or an equivalent `UPDATE … WHERE
  next_run_at <= now() AND running = FALSE RETURNING`), immediately advancing
  `next_run_at` and setting a `running`/lease marker. This guarantees a task is
  executed at most once per due tick even if two scheduler instances race, and
  a crashed lease expires so the task recovers on a later tick.

Cron is stored as a standard 5-field expression; `next_run_at` is recomputed
after each run from the cron + last fire time.

## Decision 4 — Background safety limits & destructive-tool gating

A background run cannot ask the user to confirm anything, so:

- **Destructive tools disabled.** In background mode the tool registry exposed to
  `_run_loop` excludes `delete_block` and any document/block delete path; if a
  destructive action is somehow requested it is refused and recorded, never
  executed. Optionally a task may carry an explicit pre-approval flag for a
  narrowly-scoped destructive action; absent that, destructive = off.
- **Per-run limits:** `max_tool_rounds` (default reuses/tightens
  `MAX_TOOL_ROUNDS`), `max_wall_clock_seconds`, and `max_actions` (count of
  editing/tool calls). On exceeding any limit the run stops immediately and is
  recorded with the limit that tripped it (`stopped_rounds` /
  `stopped_timeout` / `stopped_actions`).
- The background execution context is a small object threaded into the run that
  flags `background=True`, filters the tool registry, and carries the limits.

## Decision 5 — Storage schema

New migration `db/migrations/NNNN_scheduled_agents.sql`. `NNNN` is a
clearly-later number than `0011`; because other changes may also be in flight,
the implementer picks the next free number at merge time (e.g. `0012`, or higher
if another migration merged first) — filename order is what `scripts/migrate.py`
uses, so it must sort after all currently-merged migrations.

```
scheduled_agent_tasks
  id           TEXT PRIMARY KEY
  tenant_id    TEXT NOT NULL
  owner_id     TEXT NOT NULL                 -- the authorizing user
  name         TEXT NOT NULL
  instruction  TEXT NOT NULL                 -- natural-language task
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE
  document_id  TEXT REFERENCES documents(id) ON DELETE SET NULL   -- optional target
  schedule_cron TEXT                         -- 5-field cron, nullable
  trigger_kind  TEXT                         -- e.g. 'file_uploaded', nullable
  enabled      BOOLEAN NOT NULL DEFAULT TRUE
  next_run_at  TIMESTAMPTZ
  running      BOOLEAN NOT NULL DEFAULT FALSE -- lease marker for locking
  lease_until  TIMESTAMPTZ                    -- lease expiry for crash recovery
  max_tool_rounds INT NOT NULL DEFAULT 8
  max_wall_seconds INT NOT NULL DEFAULT 120
  max_actions  INT NOT NULL DEFAULT 20
  created_at   TIMESTAMPTZ NOT NULL
  updated_at   TIMESTAMPTZ NOT NULL

agent_task_runs
  id           TEXT PRIMARY KEY
  tenant_id    TEXT NOT NULL
  task_id      TEXT NOT NULL REFERENCES scheduled_agent_tasks(id) ON DELETE CASCADE
  owner_id     TEXT NOT NULL
  trigger      TEXT NOT NULL                 -- 'schedule' | 'trigger:<kind>' | 'manual'
  document_id  TEXT                          -- produced/target document
  outcome      TEXT NOT NULL                 -- 'succeeded'|'failed'|'denied'|'stopped_*'
  detail       TEXT                          -- error / limit / summary
  tools_used   JSONB NOT NULL DEFAULT '[]'
  started_at   TIMESTAMPTZ NOT NULL
  finished_at  TIMESTAMPTZ
```

Both tables `ENABLE ROW LEVEL SECURITY` with policy
`USING (tenant_id = current_setting('cyberarche.tenant_id', TRUE))`, matching
`0010`/`0011`. `agent_task_runs` extends the existing audit story in
`ports/agent.py` (it is the task-run analogue of `AgentRun`).

Domain types: `ScheduledAgentTask` and `AgentTaskRun` (frozen dataclasses),
plus new id NewTypes `ScheduledAgentTaskId` / `AgentTaskRunId` in
`domain/ids.py`. New port `ScheduledAgentRepository` (CRUD + `claim_due(now)`
for locking + run recording). Postgres repo + `InMemoryScheduledAgentRepository`
fake; a `ScheduledAgentUseCases` use case; wired into `_Repositories`,
`_memory_repositories`, `_postgres_repositories`, `UseCases`, and
`tests/conftest.py`.

## Decision 6 — Failure & retry handling

- A run that raises is caught, recorded `failed` with the error detail, the lease
  released, and `next_run_at` advanced to the next scheduled slot. We do **not**
  hot-retry within the same tick (avoids storms); the next scheduled tick retries.
- A run that hits a limit records `stopped_*` and is treated as a completed (not
  failed) run for scheduling purposes.
- A run denied by `AccessControl` (owner lost access) records `denied` and does
  not notify; repeated denials are visible in run history so the owner can fix or
  disable the task.
- Crash recovery: a lease with `lease_until < now()` is reclaimable, so a
  scheduler crash mid-run leaves the task runnable again on a later tick.

## Decision 7 — Results into a document + notification

- The run targets the task's `document_id` if set; otherwise the use case creates
  (or reuses a conventional "Agent output" doc in the workspace) and records its
  id on the run. Output blocks are applied through the CRDT, attributed to the
  agent, exactly like an interactive edit — so if anyone has the doc open, edits
  appear live.
- On success the use case emits a notification (reusing the `notifications`
  inbox, a new `kind = 'agent_task'`) to the task **owner**, carrying a link to
  the produced document and a short summary. Denied/failed runs surface in run
  history rather than as a success notification.

## Open questions / notes

- Trigger sources beyond schedule (e.g. `file_uploaded`) are modeled but only the
  schedule path is required for this change; trigger wiring can land incrementally
  behind the same task model.
- Cron parsing uses a small vetted library or a minimal 5-field evaluator; no new
  heavy dependency is mandated by the spec.
