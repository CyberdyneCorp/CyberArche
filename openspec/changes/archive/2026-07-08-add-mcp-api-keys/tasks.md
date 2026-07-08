## 1. Backend

- [x] 1.1 Domain: `ApiKey` entity (hash, prefix, owner, expiry, revocation) + key generation/hash helpers
- [x] 1.2 `ApiKeyRepository` port, in-memory fake, Postgres adapter + `0005_api_keys` migration
- [x] 1.3 `ApiKeyUseCases`: create (secret returned once), list (no secrets), revoke
- [x] 1.4 `CompositeTokenVerifier` (cak_ -> repository, else delegate) wired as `container.token_port`; last_used tracking
- [x] 1.5 HTTP router `/api/v1/api-keys` (POST/GET/DELETE)
- [x] 1.6 Tests: create/show-once/hash-at-rest, owner-scoped auth on HTTP + WS + MCP, revoked/expired rejection, contract suite for the repository

## 2. Web

- [x] 2.1 API keys section on settings: create with show-once secret + copy, connector setup hint (MCP URL + header), list with prefix/last-used, revoke
- [x] 2.2 E2E: create key in UI, secret shown once, key authenticates an MCP tool call, revoke denies it
