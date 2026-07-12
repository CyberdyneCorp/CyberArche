# Tasks

## 1. Data model (migration)
- [ ] 1.1 Add `db/migrations/NNNN_scheduled_agents.sql` (next free number after all
      merged migrations; must sort after `0011`) creating `scheduled_agent_tasks`
      and `agent_task_runs` per design.
- [ ] 1.2 Enable RLS on both tables with policy
      `tenant_id = current_setting('cyberarche.tenant_id', TRUE)`; add lookup
      indexes (`(tenant_id, next_run_at)` on due-task selection, `(tenant_id, task_id)`
      on runs).
- [ ] 1.3 Confirm `scripts/migrate.py` applies it in filename order (no code change
      expected).

## 2. Domain
- [ ] 2.1 Add `ScheduledAgentTaskId` and `AgentTaskRunId` NewTypes to `domain/ids.py`.
- [ ] 2.2 Add frozen `ScheduledAgentTask` and `AgentTaskRun` domain dataclasses
      (owner, tenant, workspace, optional document, cron/trigger, enabled, limits,
      lease fields; run: trigger, outcome, detail, timestamps).
- [ ] 2.3 Cron next-run computation helper (pure, in domain/application).

## 3. Ports
- [ ] 3.1 Add `ScheduledAgentRepository` port (create/get/list/update/enable-disable,
      `claim_due(now)` with locking semantics, `record_run`, `list_runs_for_task`).
- [ ] 3.2 Extend the audit story in `ports/agent.py` (or a sibling port) so
      `AgentTaskRun` records are first-class alongside `AgentRun`.

## 4. Repositories
- [ ] 4.1 `PostgresScheduledAgentRepository` implementing claim via
      `FOR UPDATE SKIP LOCKED` (or `UPDATE … RETURNING`) with lease + `next_run_at`
      advance; sets `cyberarche.tenant_id` per query.
- [ ] 4.2 `InMemoryScheduledAgentRepository` fake with the same claim/lease semantics.

## 5. Service-token client (auth)
- [ ] 5.1 Ensure/extend `ClientCredentialsTokenSource` to acquire a CyberArche
      service token via `POST /api/v1/auth/oauth2/token`
      (`grant_type=client_credentials`, `client_secret_basic`,
      `scope="cyberrag:query interpreter:execute"`, optional `audience`).
- [ ] 5.2 In-memory caching with refresh ~30s before expiry; shared per process.

## 6. Use case
- [ ] 6.1 `ScheduledAgentUseCases`: create/list/enable/disable tasks (owner-scoped),
      list run history.
- [ ] 6.2 `run_task(task)`: build the owner-scoped `CallerContext` from the stored
      owner + tenant; attach the service token as outbound transport only; invoke
      the existing `AgentUseCases.ask()` / `_run_loop()` with a background context.
- [ ] 6.3 Re-check owner permissions via `AccessControl` at run time; record `denied`
      if the owner no longer has access.
- [ ] 6.4 Write output into the target/created document through the CRDT; record the
      document id on the run.
- [ ] 6.5 Emit an owner notification (`kind = 'agent_task'`) with a document link on
      success.

## 7. Background execution context (safety)
- [ ] 7.1 Introduce a background execution context flag threaded into `_run_loop`
      (`background=True`).
- [ ] 7.2 Filter the tool registry in background mode to disable destructive tools
      (`delete_block`, document/block delete); refuse+record if requested.
- [ ] 7.3 Apply per-run limits: `max_tool_rounds`, `max_wall_seconds`, `max_actions`;
      stop and record `stopped_*` on exceed.

## 8. Scheduler / worker
- [ ] 8.1 Periodic scheduler (default: in-process asyncio loop in the API lifespan;
      alternative: `cyberarche-agent-scheduler` entrypoint under
      `services/cyberarche/workers`, invoked by Docker `command:`).
- [ ] 8.2 On each tick, `claim_due(now)` and dispatch each claimed task to
      `run_task`; advance `next_run_at`; release lease in a `finally`.
- [ ] 8.3 Crash recovery: reclaim leases past `lease_until`.

## 9. Audit extension
- [ ] 9.1 Every run writes an `agent_task_runs` record (task id, owner, trigger,
      outcome, detail, tools_used, timestamps) — success, failure, denied, stopped.

## 10. HTTP router
- [ ] 10.1 FastAPI router (thin, delegates to `ScheduledAgentUseCases`):
      create/list/enable/disable tasks and list run history; caller resolved from
      the verified user token; owner set from the caller.
- [ ] 10.2 DomainError→HTTP mapping via the existing seam.

## 11. Wiring
- [ ] 11.1 Add the repository to `_Repositories`, `_memory_repositories`,
      `_postgres_repositories`; add `ScheduledAgentUseCases` to `UseCases`; start the
      scheduler from the composition root.
- [ ] 11.2 Add the fake to `tests/conftest.py` fixtures.
- [ ] 11.3 Keep import-linter contracts green (inbound never imports outbound).

## 12. Frontend (SvelteKit + Svelte 5 runes, MVVM)
- [ ] 12.1 Typed API client (`lib/api/`) for tasks + run history DTOs.
- [ ] 12.2 ViewModel (`*.svelte.ts`, `$state`/`$derived`, singleton + factory) for
      task list/create/enable/disable.
- [ ] 12.3 Views: create/list/enable/disable tasks; run-history panel with a link to
      the produced document.

## 13. Tests
- [ ] 13.1 Owner-scoped authorization: a background run acts within the owner's
      tenant/permissions; a run whose owner lost access is `denied`; no cross-tenant
      leakage.
- [ ] 13.2 Safety: destructive tools unavailable in background mode; each limit
      (rounds/time/actions) stops and records the correct `stopped_*`.
- [ ] 13.3 Locking: two concurrent claim attempts run a due task at most once; a
      stale lease is reclaimable.
- [ ] 13.4 Service token: acquired via client-credentials, cached, refreshed before
      expiry; used only as outbound transport, not as run authority.
- [ ] 13.5 Results: output lands in the target document via CRDT and an owner
      notification with a document link is emitted on success.
- [ ] 13.6 Repository parity: Postgres and in-memory fakes behave identically.

## 14. Spec / docs
- [ ] 14.1 `openspec validate autonomous-agents --strict` → zero errors.
- [ ] 14.2 Update project docs if behavior/wiring changed.
