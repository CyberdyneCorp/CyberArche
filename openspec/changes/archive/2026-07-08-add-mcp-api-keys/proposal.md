## Why

External MCP clients (Claude Desktop/claude.ai connectors, ChatGPT, other
agents) authenticate with a static bearer credential configured once. Our only
credentials today are CyberdyneAuth JWTs, which expire in minutes — unusable in
a connector configuration. Users need personal, long-lived, revocable API keys
they can mint in the UI and paste into Claude/ChatGPT to reach the CyberArche
MCP server securely.

## What Changes

- **Personal API keys**: create (named, optional expiry), list (prefix only),
  and revoke — in the settings UI and over HTTP. The secret is shown exactly
  once at creation; only a SHA-256 hash is stored.
- **Verification**: the token verifier accepts `cak_…` API keys alongside
  JWTs on every inbound surface (HTTP, WebSocket relay, MCP tools). A key
  authenticates as its owning user with that user's permissions — nothing more.
- **Lifecycle**: revocation and expiry deny immediately; last-used is tracked.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `auth-integration`: adds the API-key credential type (issuance, hashing,
  verification, revocation, expiry).
- `mcp-server`: authenticated tools accept API keys, enabling external MCP
  clients to connect.

## Impact

- **Domain** `libs/cyberarche/domain`: `ApiKey` entity.
- **Application**: `ApiKeyRepository` port, `ApiKeyUseCases`, composite
  token verifier (API key → fall through to JWT/introspection).
- **Adapters**: Postgres repository + migration `0005_api_keys`, HTTP router
  `/api/v1/api-keys`, wiring.
- **Web**: API keys section on the settings page (create with show-once
  secret + copy, list, revoke, connector setup hint).
- **Data**: new `api_keys` table (hash-indexed).
