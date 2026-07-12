# Tasks — Google Workspace connector

## 1. Data model / migration

- [ ] Add `db/migrations/0014_google_connections.sql` (number clearly later than
      `0011_templates.sql`; renumber to the next free slot if another in-flight
      change claims `0012` first).
- [ ] Table `google_connections`: `id` (PK), `tenant_id`, `workspace_id`,
      `user_id`, `google_email`, `access_token_encrypted`,
      `refresh_token_encrypted`, `token_expires_at`, `scopes` (granted),
      `status` (`connected`/`needs_reconnect`/`disconnected`), timestamps.
- [ ] `UNIQUE (tenant_id, workspace_id, user_id)` — one connection per user per
      workspace.
- [ ] `ENABLE ROW LEVEL SECURITY` + policy
      `tenant_id = current_setting('cyberarche.tenant_id', TRUE)`.

## 2. Domain

- [ ] Add `GoogleConnectionId` to `domain/ids.py`.
- [ ] `domain/google_workspace.py`: `GoogleConnection` aggregate (scopes, status,
      expiry helpers), scope/tool-group value objects, status transitions
      (`connect`, `mark_needs_reconnect`, `disconnect`).
- [ ] Domain never touches I/O or plaintext token storage decisions.

## 3. Application port

- [ ] `application/ports/google_workspace.py`: `GoogleWorkspacePort` Protocol for
      the OAuth flow (build consent URL, exchange code, refresh, revoke) and
      Gmail / Calendar / Drive / Docs REST calls, plus a
      `GoogleConnectionRepository` Protocol (add/get/update/delete, returning and
      accepting encrypted token bytes; never plaintext).
- [ ] Reuse existing `SecretBoxPort` for encryption (no new secret mechanism).

## 4. Outbound Google adapter

- [ ] `adapters/outbound/google/oauth.py`: build consent URL with minimal scopes
      + signed `state`; exchange code; auto-refresh access token; revoke on
      disconnect; re-encrypt rotated tokens.
- [ ] `adapters/outbound/google/gmail.py`: search, read, create draft (compose);
      send only when explicitly invoked by a confirmed user action.
- [ ] `adapters/outbound/google/calendar.py`: list events, `find_free_busy`,
      create event (explicit action only).
- [ ] `adapters/outbound/google/drive.py` + `docs.py`: search Drive, read files,
      fetch Doc structure, map Doc → CyberArche blocks.
- [ ] Map Google HTTP 401/403/quota errors to clear domain errors; never log
      tokens.

## 5. Encrypted-token repository

- [ ] `adapters/outbound/postgres/google_connections.py`: `PostgresGoogleConnectionRepository`
      over `google_connections`, envelope-encrypting tokens via `SecretBoxPort`;
      metadata readable, secrets never returned in plaintext.
- [ ] `InMemoryGoogleConnectionRepository` fake in
      `application/testing/fakes.py`.

## 6. Use case

- [ ] `application/use_cases/google_workspace.py`: `connect` (start OAuth),
      `complete_connect` (handle callback, store encrypted tokens + granted
      scopes), `disconnect` (revoke + remove), `status`, and per-tool operations
      (gmail search/read/draft, calendar list/free-busy/create, drive search/read,
      doc import) that resolve the connection strictly by the current caller's
      `user_id` + `workspace_id` and check the required scope first.

## 7. Agent tools

- [ ] In `application/use_cases/agent.py`, register Google tools **gated on the
      caller having a connected Google account with the required scope** (absent
      otherwise), following the existing per-user meetings-tool pattern.
- [ ] Compose and create-event tools produce a **draft / confirmation**, not an
      autonomous send/create.
- [ ] Doc-import results and read results are insertable and citable via the
      existing block-insert path.

## 8. Inbound MCP read tools

- [ ] Expose Gmail/Calendar/Drive **read** tools via the inbound MCP server
      (`adapters/inbound/mcp/…`) acting as the connected caller. Never expose
      send/create over MCP.

## 9. OAuth callback HTTP routes

- [ ] `adapters/inbound/http/routers/google.py`: connect (redirect to Google),
      OAuth callback (verify `state`, exchange code), disconnect. Thin — delegate
      to the use case. Register the router in the API factory.

## 10. Wiring

- [ ] Extend `_Repositories`, `_memory_repositories`, `_postgres_repositories`,
      and `UseCases` in `adapters/wiring/__init__.py` with the Google connection
      repository, the Google port adapter, and the new use case; reuse the
      existing `secret_box`.
- [ ] Extend `tests/conftest.py` with the in-memory Google fixtures.

## 11. Frontend (SvelteKit + Svelte 5 runes, MVVM)

- [ ] Settings UI to **connect / disconnect Google** and show connection status
      + connected email.
- [ ] Per-tool-group consent (Gmail / Calendar / Docs-Drive) so a user grants
      only the scopes they want.
- [ ] Typed API client (Model) + ViewModel; View never calls the API directly.

## 12. Permission / privacy checks

- [ ] A connection is personal: the agent uses it only for the connecting user's
      own requests; no path resolves another user's connection.
- [ ] Tenant isolation via RLS + verified-claim `tenant_id` on every query.
- [ ] Disconnect revokes tokens so no further access is possible.
- [ ] Tokens never returned in plaintext or logged.

## 13. Tests

- [ ] Domain tests: status transitions, scope checks, Doc→block mapping.
- [ ] Use-case tests (in-memory fakes): connect/complete/disconnect; scope-gating;
      send/create require explicit action; per-user isolation (user B cannot use
      user A's connection); tenant isolation.
- [ ] Adapter tests: token encryption round-trip; auto-refresh; revoke on
      disconnect; Google error mapping.
- [ ] HTTP route tests: `state` verification, callback happy path + failure.
- [ ] Regression test for the confirmation-before-send guarantee.

## 14. Spec / docs

- [ ] Keep `specs/google-workspace-connector/spec.md` in sync with behaviour.
- [ ] Note in `openspec/project.md` (or connector docs) that Google Workspace is
      the ONLY first-party SaaS connector; all other SaaS use external-MCP.
- [ ] `openspec validate google-workspace-connector --strict` passes.
