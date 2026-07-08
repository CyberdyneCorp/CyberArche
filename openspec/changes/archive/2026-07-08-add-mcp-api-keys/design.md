## Context

External MCP clients configure one static bearer credential. CyberdyneAuth
access tokens expire in minutes; refresh flows are not available inside
Claude/ChatGPT connector configs. The MCP server, HTTP API, and WS relay all
authenticate through the single `container.token_port`.

## Goals / Non-Goals

**Goals:** long-lived personal keys, hashed at rest, shown once, revocable,
verified on all surfaces through the existing token seam.

**Non-Goals:** scoped/limited keys (a key = its owner, nothing less or more);
org-level service keys (CyberdyneAuth client-credentials already covers
service identity); OAuth for MCP clients.

## Decisions

### D-1 — Keys ride the existing TokenPort seam
A `CompositeTokenVerifier` implements `TokenPort`: secrets with the `cak_`
prefix resolve via `ApiKeyRepository` (SHA-256 hash lookup → owner claims);
anything else falls through to the existing JWKS/introspection verifier.
Wired once in the composition root, so HTTP, WS, and MCP accept keys with
zero changes to routers, relay, or tools. **Alternative rejected:** a parallel
auth dependency per surface — would triple the enforcement points.

### D-2 — Key format and storage
`cak_<43 chars urlsafe(32 bytes)>`. Stored: SHA-256(secret) (indexed, unique),
name, non-secret display prefix (`cak_…8`), owner user/tenant from the
creating caller's verified claims, optional expiry, revoked_at, last_used_at
(updated on successful verification). Lookup by exact hash is constant-time
by construction.

### D-3 — Keys act strictly as their owner
Claims minted from a key are `subject=owner user, tenant=owner tenant,
is_service=False`. All authorization continues to flow through the same
use-case checks, so a key can never exceed the owner's permissions.

## Risks / Trade-offs

- A leaked key is a long-lived credential → shown once, revocation is
  immediate (checked per request), last_used_at surfaces abuse, optional
  expiry at creation.
- last_used_at write per request adds a small hot-path write → fire-and-forget
  update, no transaction.

## Migration Plan

Additive migration `0005_api_keys`; no changes to existing tables. Rollback:
drop table (keys stop verifying; JWT auth unaffected).
