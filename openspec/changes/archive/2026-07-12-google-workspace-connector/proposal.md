# Google Workspace connector (first-party)

## Why

CyberArche's agent can already reach in-house Cyberdyne tools (Slack, Jira, and
similar SaaS) through the existing generic **external-MCP connectors**
(`openspec/specs/external-mcp-connectors/spec.md`): a user registers the tool's
MCP endpoint with encrypted credentials and its namespaced tools become
available in scope. Those integrations do not need first-party code.

Google Workspace is different. There is no in-house MCP wrapper for a user's
personal Gmail / Calendar / Drive, the data is strictly per-user, and access
requires a real Google OAuth2 authorization-code flow with refreshing tokens —
not a static credential a user can paste. To let the agent read a caller's
mail, find free/busy times and schedule meetings, and pull in Google Docs, we
need a **first-party** connector that owns the OAuth handshake, stores the
tokens encrypted per user, and exposes gated agent tools.

Product decision: **Google Workspace is the ONLY first-party SaaS connector.**
Every other SaaS integration (Slack, Jira, etc.) remains served by the generic
external-MCP connectors and is explicitly out of scope here. This connector also
closes the "meeting scheduling" gap versus Notion by adding Calendar free/busy +
event creation.

## What Changes

- **New capability `google-workspace-connector`.** Per-user Google OAuth2
  (authorization-code + refresh token) that a user connects and disconnects from
  settings, with minimal scopes requested per tool group.
- **Gmail tools** (agent): search and read the caller's mail; draft/compose a
  reply or new message. **Sending requires an explicit user action** — the agent
  never sends silently.
- **Calendar tools** (agent): list events, **find free/busy times**, and create
  events. **Creating an event requires an explicit user action.**
- **Docs / Drive tools** (agent): search and read Docs/Drive files; **import a
  Google Doc into a CyberArche document as blocks** that are insertable and
  citable.
- **Encrypted per-user token storage.** OAuth access/refresh tokens, granted
  scopes, and connection status stored encrypted at rest per `user + workspace`,
  reusing the connectors' envelope-encryption approach (`SecretBoxPort` /
  `FernetSecretBox`). Tokens refresh automatically; plaintext is never returned.
- **Data model:** new `google_connections` table via a numbered migration, with
  tenant-isolation RLS.
- **Read tools also exposed via the inbound MCP server**, so an MCP client acting
  as the connected user can search/read Gmail/Calendar/Drive (never send/create).
- **OAuth callback HTTP routes** for connect/disconnect and the Google redirect.
- **Frontend (SvelteKit + Svelte 5 runes):** settings UI to connect/disconnect
  Google and grant per-tool-group consent.
- **Explicitly out of scope:** Slack, Jira, and every other SaaS — served by the
  existing external-MCP connectors.

## Impact

- **Affected specs:** NEW capability `google-workspace-connector`. No edits to
  existing specs; the external-MCP-connectors spec is referenced only to align
  credential-encryption language and to scope out non-Google SaaS.
- **Affected code (implementation, not in this change):**
  - Domain: new `GoogleConnection` aggregate + `GoogleConnectionId`, scopes,
    status.
  - Application: port `application/ports/google_workspace.py`; new use case
    `use_cases/google_workspace.py`; agent tools added in
    `use_cases/agent.py` (gated on a connected Google account); in-memory fake.
  - Adapters: outbound `adapters/outbound/google/…` (OAuth flow + Gmail /
    Calendar / Drive REST); Postgres repo for encrypted tokens; inbound HTTP
    OAuth callback router; inbound MCP read tools; wiring
    (`_Repositories` / `_memory_repositories` / `_postgres_repositories` /
    `UseCases`), `tests/conftest.py`.
  - Frontend: settings connect/disconnect + per-tool consent (MVVM).
- **Data model:** `db/migrations/NNNN_google_connections.sql` — a number
  clearly later than `0011_templates.sql` (proposed `0014`; renumber to the next
  free slot if another in-flight change lands a `0014` first). Per `user +
  workspace` row with encrypted tokens, granted scopes, and status; RLS
  `tenant_id = current_setting('cyberarche.tenant_id', TRUE)`.
- **OAuth / security:** a new external identity provider (Google) distinct from
  CyberdyneAuth. Refresh tokens are long-lived secrets — encrypted at rest,
  never logged, never returned in plaintext. Minimal scopes per tool group.
- **Privacy / isolation:** a connection is personal to the connecting user; the
  agent may use it only for that user's own requests. One user's Google data is
  never exposed to another user, and all storage/queries respect tenant
  isolation. Disconnecting revokes the tokens and removes access.
- **Risks:** OAuth token leakage (mitigated by envelope encryption + no
  plaintext egress + revoke on disconnect); scope creep (mitigated by
  per-tool-group minimal scopes and per-tool consent); accidental send/create
  (mitigated by mandatory explicit user confirmation); Google API quota/rate
  limits (mitigated by read-mostly usage and surfacing clear errors).
