# Design — Google Workspace connector

## Context

CyberArche is hexagonal (`domain <- application <- adapters`, inbound never
imports outbound, enforced by import-linter). Auth/tenant scope comes from
verified token claims. External MCP connectors already give the agent third-party
tools via a generic mechanism; this change adds the one first-party SaaS
connector — Google Workspace — because Google needs a real per-user OAuth2 flow
with refreshing tokens that the generic connector cannot express.

## Relationship to external-MCP connectors (scope boundary)

- The generic `external-mcp-connectors` capability stays the home for every
  other SaaS (Slack, Jira, …): the user registers an in-house Cyberdyne MCP
  endpoint with a static encrypted credential and gets namespaced tools.
- `google-workspace-connector` is **first-party and the only one**. Rationale:
  - No paste-able static credential exists for a user's personal Google account;
    it requires an interactive OAuth2 authorization-code grant.
  - Tokens expire and must be refreshed automatically using a stored refresh
    token — behaviour the generic connector does not own.
  - The data is strictly per-user and needs per-user consent and isolation.
- We deliberately reuse the connectors' **envelope-encryption** approach
  (`SecretBoxPort` implemented by `FernetSecretBox`, keyed by
  `connector_secret_key`; `NaiveSecretBox` fake in tests) rather than inventing a
  second secret-storage mechanism.

## Decision: per-user OAuth2 (authorization-code + refresh)

- **Grant:** authorization-code with `access_type=offline` and
  `prompt=consent` so Google returns a **refresh token**. We store an anti-CSRF
  `state` bound to `user + workspace` and verify it on callback.
- **Flow:**
  1. User clicks *Connect Google* in settings for a workspace.
  2. Backend builds the Google consent URL with the minimal scopes for the tool
     groups the user is enabling, and a signed `state`.
  3. Google redirects back to the connector's callback route with `code`.
  4. Backend exchanges `code` for access + refresh tokens, records the actually
     granted scopes, and stores everything encrypted.
- **Refresh:** the outbound adapter refreshes the access token automatically when
  it is expired/near-expiry using the stored refresh token; the new access token
  (and rotated refresh token, if Google rotates it) is re-encrypted and saved.
  Refresh failure (revoked/expired) flips the connection `status` to
  `needs_reconnect` and surfaces a clear "reconnect Google" error.
- **Why not delegate the caller's Cyberdyne token** (as the meetings port does):
  Google is a different identity provider than CyberdyneAuth, so there is no
  Cyberdyne token Google would accept. We must hold Google's own tokens.

## Decision: scope minimization per tool group

Request only what a group needs, and only the groups the user consents to:

| Tool group | Scope(s) | Actions |
| --- | --- | --- |
| Gmail read | `gmail.readonly` | search, read |
| Gmail compose | `gmail.compose` | draft; send only on explicit user action |
| Calendar | `calendar` (events read + write) | list, free/busy, create (create only on explicit user action) |
| Docs/Drive read | `drive.readonly`, `documents.readonly` | search, read, import a Doc |

- A user who enables only Calendar never grants Gmail/Drive scopes.
- Granted scopes are stored on the connection; each tool checks that its required
  scope is present before running and otherwise returns a "grant this permission"
  error rather than calling Google.

## Decision: encrypted token storage

- New `google_connections` row per `user + workspace` (unique together) holding:
  encrypted access token, encrypted refresh token, token expiry, granted scopes,
  `status` (`connected` | `needs_reconnect` | `disconnected`), timestamps, and
  the connecting `user_id` / `tenant_id`.
- Tokens are envelope-encrypted with `SecretBoxPort`; the repository accepts and
  returns ciphertext, and **plaintext tokens are never returned to callers or
  logged**. Metadata (status, scopes, connected email) is readable; secrets are
  not — mirroring the connectors' "credentials not readable" requirement.
- RLS: `ENABLE ROW LEVEL SECURITY` with policy
  `tenant_id = current_setting('cyberarche.tenant_id', TRUE)`.

## Decision: confirmation before send/create

- **Read/find tools** (Gmail search/read, Calendar list/free-busy, Docs/Drive
  search/read/import) can run autonomously within the connected user's request.
- **Mutating tools with external side effects** — Gmail *send* and Calendar
  *create event* — **require an explicit user action**. The agent's compose tool
  only produces a **draft** (saved as a Gmail draft and/or shown for review); the
  actual send happens when the user confirms. Likewise "create event" is
  surfaced for the user to confirm/trigger. This keeps the agent from
  autonomously emailing people or booking meetings.

## Decision: Calendar free/busy for scheduling

- A `find_free_busy` tool queries Google's free/busy API over a time window
  (optionally across the user's calendars) and returns open slots, closing the
  meeting-scheduling gap versus Notion.
- The agent can propose slots from free/busy output, then a **create-event**
  action (explicit confirmation) books the chosen slot.

## Decision: importing a Google Doc into CyberArche blocks

- `import_doc(doc_id)` fetches the Doc structure via the Docs API and maps it to
  CyberArche block types: headings → heading blocks, paragraphs → text blocks,
  lists → list blocks, tables → table blocks, code-styled content → code blocks;
  unsupported elements degrade to text with a note.
- The mapped blocks reuse the agent's existing insert path so they are inserted
  as first-class CRDT blocks, are **insertable and citable**, and carry a source
  reference back to the originating Doc.

## Decision: exposure surfaces

- **Agent use case** registers the Google tools, **gated on the caller having a
  connected Google account** (with the required scope); tools are absent when no
  connection exists.
- **Inbound MCP server** exposes the **read** tools only (Gmail/Calendar/Drive
  search+read) acting as the connected user, so an MCP client gets the same
  read surface. Send/create are never exposed over MCP.

## Isolation & privacy

- A connection is personal to the connecting user. The use case resolves the
  Google connection strictly by the **current caller's** `user_id` +
  `workspace_id`; there is no path to use another user's connection.
- One user's Google data is never returned to another user. Tenant isolation is
  enforced by RLS and by carrying `tenant_id` from verified claims.
- **Disconnect** revokes the tokens at Google (best-effort) and deletes/So
  marks the stored tokens so no further access is possible.

## Alternatives considered

- **Model Google as another external-MCP connector** — rejected: no static
  credential, no automatic refresh, no per-tool OAuth consent.
- **Store tokens plaintext** — rejected: refresh tokens are long-lived secrets;
  we already have envelope encryption for connector credentials.
- **Let the agent send/create autonomously** — rejected: unacceptable side
  effects (emailing people, booking meetings) without user intent.
