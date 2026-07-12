# Autonomous scheduled agents

## Why

Today every agent run is interactive: a live user opens a document, types an
instruction, and the agent answers with their bearer token in hand. There is no
way to say "every Monday at 08:00, draft a status summary of this workspace into
this document" or "when a new file lands, ingest and summarize it" — the run
needs a live user to authorize it, to confirm destructive steps, and to receive
the answer.

Notion 3.0 "Custom Agents" set the bar: users configure an agent task once, and
it runs on its own — on a schedule or a trigger — in the background, writes the
result into a document, and notifies them. CyberArche should match this while
respecting our stricter constraints: CyberdyneAuth has **no on-behalf-of /
delegation grant**, so a background run has no user token and must authenticate
as the service itself, yet it must still act with the *permissions of the user
who created the task*, never with the service identity's reach.

## What Changes

- **New capability: scheduled autonomous agent tasks.** A user creates a
  `ScheduledAgentTask` (name, natural-language instruction, target workspace,
  optional target document, and a cron-like schedule and/or a trigger). Tasks
  can be enabled/disabled and listed with their run history.
- **Background execution through the existing tool-loop.** A background run
  invokes the same `ask()` / `_run_loop()` in the agent use case, but with a
  *background execution context*: no live token (a service token is used
  instead), **destructive tools disabled** (no `delete_block` / delete
  document), and hard per-run limits (max tool rounds, max wall-clock, max
  actions).
- **Owner-scoped authorization (auth-critical).** Because the client-credentials
  service token is `client:<id>` and carries no end-user identity, the run's
  tenant and permissions are derived from the task's **stored owner** (the user
  who created it), and the run executes strictly within that owner's tenant and
  document/workspace permissions — the service token is only a transport
  credential to sibling backends (CyberRAG, interpreter), never the authority.
- **A scheduler/worker.** A periodic scheduler evaluates due tasks and enqueues
  runs, with single-run locking so one task is never double-executed on a tick.
- **Results + notification.** Each run writes its output into the target document
  (through the CRDT, attributed to the agent) and emits a notification to the
  owner with a link to the produced document.
- **Audit + data model.** Every run writes an `AgentTaskRun` audit record (task
  id, owner, trigger, outcome, limits hit). A numbered migration adds the task
  and run tables with tenant RLS.
- **Auth-integration delta.** Add a requirement for CyberArche obtaining, caching
  and refreshing its own OAuth2 client-credentials **service token** for
  background work (distinct from user-bearer forwarding used interactively).
- **Frontend.** SvelteKit + Svelte 5 (runes, MVVM) UI to create / list / enable /
  disable tasks and view run history with a link to the produced document.

## Impact

- **Affected specs:** `ai-agent` (ADDED: scheduled runs, background safety
  limits, owner-scoped background authorization), `auth-integration` (ADDED:
  CyberArche service token for background work).
- **Auth impact (critical):** introduces a non-interactive authorization path.
  Interactive runs forward the caller's user bearer (unchanged). Background runs
  authenticate the service with a cached client-credentials token *and*
  authorize against the stored task owner. Getting this wrong would either let a
  background run act with service-wide reach (privilege escalation) or leak
  across tenants — the design pins both down.
- **Data-model impact:** new numbered migration
  `db/migrations/NNNN_scheduled_agents.sql` (a clearly-later number than `0011`;
  see design for ordering vs other in-flight changes) creating
  `scheduled_agent_tasks` and `agent_task_runs`, both with RLS
  `tenant_id = current_setting('cyberarche.tenant_id', TRUE)`. New domain types,
  port(s), a Postgres repository plus an in-memory fake, a use case, and wiring
  in `_Repositories` / `_memory_repositories` / `_postgres_repositories` /
  `UseCases` / `tests/conftest.py`.
- **Runtime impact:** a periodic scheduler runs in the deployment (in-process
  asyncio loop or a `services/cyberarche/workers` entrypoint); migrations already
  run before the API via `scripts/migrate.py`. Single-instance Coolify friendly;
  locking keeps a task from double-running.
- **Risks:** runaway loops (mitigated by round/time/action limits), destructive
  side effects with no human to confirm (mitigated by disabling destructive
  tools in background mode), double execution (mitigated by row-level locking on
  claim), and authorization drift if the owner later loses access (re-checked at
  run time against the owner's current permissions).
